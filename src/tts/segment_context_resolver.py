"""Resolves per-segment TTS context: text continuity, request ID chaining, and scene modifiers.

Extracted from ``TTSOrchestrator._synthesise_segments`` so that context
resolution is independently testable and the orchestrator stays focused on
file I/O and sequencing.

Responsibilities
----------------
1. Same-character **previous_text / next_text** for prosody continuity.
2. Per-voice **previous_request_ids** sliding window for acoustic continuity.
3. **Scene-based voice modifiers** — additive deltas on top of the segment's
   emotion-based voice settings.
"""
from dataclasses import dataclass
from typing import Optional

from src.domain.models import Scene, SceneRegistry, Segment



def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))


# -- Public result dataclass ---------------------------------------------------


@dataclass
class SegmentContext:
    """All TTS context resolved for a single segment."""

    previous_text: Optional[str] = None
    next_text: Optional[str] = None
    previous_request_ids: Optional[list[str]] = None
    voice_stability: Optional[float] = None
    voice_style: Optional[float] = None
    voice_speed: Optional[float] = None


# -- Resolver ------------------------------------------------------------------


class SegmentContextResolver:
    """Resolves TTS context for each segment in a chapter.

    Instantiate once per chapter with the list of speakable segments and
    an optional :class:`SceneRegistry`.  Call :meth:`resolve` for each
    segment index (in order) to get the full context, then
    :meth:`record_request_id` after each synthesis call to feed the
    request ID sliding window.

    Args:
        segments: Ordered list of speakable segments (NARRATION / DIALOGUE only).
        scene_registry: Optional :class:`SceneRegistry` for per-segment
                        scene lookup.  When a segment's ``scene_id``
                        matches an entry, additive voice-setting modifiers
                        are applied from the scene's ``voice_modifiers``.
    """

    def __init__(
        self,
        segments: list[Segment],
        *,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> None:
        self._segments = segments
        self._scene_registry = scene_registry

        # Pre-build per-character index: character_id -> list of indices
        self._char_indices: dict[str, list[int]] = {}
        for i, seg in enumerate(segments):
            cid = seg.character_id or "narrator"
            self._char_indices.setdefault(cid, []).append(i)

        # Per-voice sliding window of request IDs (max 3).
        self._voice_request_ids: dict[str, list[str]] = {}

    # -- Public API -----------------------------------------------------------

    def resolve(
        self,
        seg_index: int,
        voice_id: Optional[str] = None,
        apply_scene_modifiers: bool = True,
    ) -> SegmentContext:
        """Resolve all TTS context for segment at *seg_index*.

        Args:
            seg_index: Index into the segments list passed at construction.
            voice_id: ElevenLabs voice ID for request-ID window lookup.
                      Pass ``None`` if request-ID chaining is not needed.
            apply_scene_modifiers: When ``False``, scene-based voice modifiers
                                   are not applied. When ``True`` (default),
                                   they are applied if available.

        Returns:
            A :class:`SegmentContext` with all resolved fields.
        """
        segment = self._segments[seg_index]
        character_id = segment.character_id or "narrator"

        # Same-character text context
        prev_text = self._find_same_char_prev(seg_index, character_id)
        nxt_text = self._find_same_char_next(seg_index, character_id)

        # Request-ID window
        prev_req_ids: Optional[list[str]] = None
        if voice_id is not None:
            window = self._voice_request_ids.get(voice_id)
            if window:
                prev_req_ids = list(window)

        # Voice settings with scene modifiers
        voice_stability = segment.voice_stability
        voice_style = segment.voice_style
        voice_speed = segment.voice_speed

        # Per-segment scene lookup from registry.
        effective_scene: Optional[Scene] = None
        if apply_scene_modifiers and self._scene_registry is not None and segment.scene_id is not None:
            effective_scene = self._scene_registry.get(segment.scene_id)

        if effective_scene is not None and voice_stability is not None:
            mods = effective_scene.voice_modifiers
            if mods:
                stability_delta = mods.get("stability_delta", 0.0)
                style_delta = mods.get("style_delta", 0.0)
                speed = mods.get("speed", voice_speed)
                voice_stability = _clamp(voice_stability + stability_delta)
                if voice_style is not None:
                    voice_style = _clamp(voice_style + style_delta)
                voice_speed = speed

        return SegmentContext(
            previous_text=prev_text,
            next_text=nxt_text,
            previous_request_ids=prev_req_ids,
            voice_stability=voice_stability,
            voice_style=voice_style,
            voice_speed=voice_speed,
        )

    def record_request_id(
        self,
        voice_id: str,
        request_id: Optional[str],
    ) -> None:
        """Record a synthesis request ID for the given voice.

        Maintains a sliding window of up to 3 IDs per voice.  ``None``
        values are silently ignored.
        """
        if request_id is None:
            return
        window = self._voice_request_ids.setdefault(voice_id, [])
        window.append(request_id)
        if len(window) > 3:
            self._voice_request_ids[voice_id] = window[-3:]

    # -- Private helpers ------------------------------------------------------

    def _find_same_char_prev(
        self,
        current_idx: int,
        character_id: str,
    ) -> Optional[str]:
        """Return text of the previous segment by the same character, or None."""
        indices = self._char_indices.get(character_id, [])
        pos = indices.index(current_idx)
        if pos > 0:
            return self._segments[indices[pos - 1]].text
        return None

    def _find_same_char_next(
        self,
        current_idx: int,
        character_id: str,
    ) -> Optional[str]:
        """Return text of the next segment by the same character, or None."""
        indices = self._char_indices.get(character_id, [])
        pos = indices.index(current_idx)
        if pos < len(indices) - 1:
            return self._segments[indices[pos + 1]].text
        return None
