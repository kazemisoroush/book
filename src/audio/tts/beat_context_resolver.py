"""Resolves per-beat TTS context: text continuity and request ID chaining."""
from dataclasses import dataclass
from typing import Optional

from src.domain.beat import Beat


@dataclass
class BeatContext:
    """All TTS context resolved for a single beat."""

    previous_text: Optional[str] = None
    next_text: Optional[str] = None
    previous_request_ids: Optional[list[str]] = None


class BeatContextResolver:
    """Resolves TTS context for each beat in a chapter."""

    def __init__(self, beats: list[Beat]) -> None:
        self._beats = beats

        self._char_indices: dict[str, list[int]] = {}
        for i, seg in enumerate(beats):
            cid = seg.character_id or "narrator"
            self._char_indices.setdefault(cid, []).append(i)

        self._voice_request_ids: dict[str, list[str]] = {}

    def resolve(
        self,
        beat_index: int,
        voice_id: Optional[str] = None,
    ) -> BeatContext:
        """Resolve all TTS context for beat at *beat_index*."""
        beat = self._beats[beat_index]
        character_id = beat.character_id or "narrator"

        prev_text = self._find_same_char_prev(beat_index, character_id)
        nxt_text = self._find_same_char_next(beat_index, character_id)

        prev_req_ids: Optional[list[str]] = None
        if voice_id is not None:
            window = self._voice_request_ids.get(voice_id)
            if window:
                prev_req_ids = list(window)

        return BeatContext(
            previous_text=prev_text,
            next_text=nxt_text,
            previous_request_ids=prev_req_ids,
        )

    def record_request_id(
        self,
        voice_id: str,
        request_id: Optional[str],
    ) -> None:
        """Record a synthesis request ID for the given voice; keeps a window of 3."""
        if request_id is None:
            return
        window = self._voice_request_ids.setdefault(voice_id, [])
        window.append(request_id)
        if len(window) > 3:
            self._voice_request_ids[voice_id] = window[-3:]

    def _find_same_char_prev(
        self,
        current_idx: int,
        character_id: str,
    ) -> Optional[str]:
        """Return text of the previous beat by the same character, or None."""
        indices = self._char_indices.get(character_id, [])
        pos = indices.index(current_idx)
        if pos > 0:
            return self._beats[indices[pos - 1]].text
        return None

    def _find_same_char_next(
        self,
        current_idx: int,
        character_id: str,
    ) -> Optional[str]:
        """Return text of the next beat by the same character, or None."""
        indices = self._char_indices.get(character_id, [])
        pos = indices.index(current_idx)
        if pos < len(indices) - 1:
            return self._beats[indices[pos + 1]].text
        return None
