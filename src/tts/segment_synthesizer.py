"""SegmentSynthesizer — provider calls and feature flag gating for individual segments.

Responsibilities
----------------
1. Call the injected TTSProvider for each segment.
2. Apply feature flags (emotion, voice_design) via constructor injection.
3. Gate optional parameters based on enabled flags:
   - emotion: only pass if emotion_enabled
   - voice_stability, voice_style, voice_speed: only pass if voice_design_enabled
"""
from pathlib import Path

from src.domain.models import Segment
from src.tts.segment_context_resolver import SegmentContext
from src.tts.tts_provider import TTSProvider


class SegmentSynthesizer:
    """Owns provider calls and feature flag gating for individual segments."""

    def __init__(
        self,
        provider: TTSProvider,
        emotion_enabled: bool = True,
        voice_design_enabled: bool = True,
    ) -> None:
        """Initialize with a TTS provider and feature flags.

        Args:
            provider: TTSProvider instance for synthesizing audio.
            emotion_enabled: When True, emotion tags are passed to provider.
            voice_design_enabled: When True, voice design parameters are passed.
        """
        self._provider = provider
        self._emotion_enabled = emotion_enabled
        self._voice_design_enabled = voice_design_enabled

    def synthesize_segment(
        self,
        segment: Segment,
        voice_id: str,
        output_path: Path,
        context: SegmentContext,
    ) -> str | None:
        """Synthesize one segment with feature flags applied.

        Applies feature flags via constructor-injected values:
        - emotion_enabled: gates segment.emotion
        - voice_design_enabled: gates voice_stability, voice_style, voice_speed

        Args:
            segment: Segment to synthesize.
            voice_id: Voice ID to use.
            output_path: Path to write MP3 to.
            context: SegmentContext with continuity and voice modifiers.

        Returns:
            request_id from provider, or None if not available.
        """
        # Apply feature flags
        emotion = segment.emotion if self._emotion_enabled else None
        voice_stability = (
            context.voice_stability if self._voice_design_enabled else None
        )
        voice_style = context.voice_style if self._voice_design_enabled else None
        voice_speed = context.voice_speed if self._voice_design_enabled else None

        # Call provider with gated parameters
        return self._provider.synthesize(
            segment.text,
            voice_id,
            output_path,
            emotion=emotion,
            previous_text=context.previous_text,
            next_text=context.next_text,
            voice_stability=voice_stability,
            voice_style=voice_style,
            voice_speed=voice_speed,
            previous_request_ids=context.previous_request_ids,
        )
