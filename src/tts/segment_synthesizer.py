"""SegmentSynthesizer — provider calls and feature flag gating for individual segments.

Responsibilities
----------------
1. Call the injected TTSProvider for each segment.
2. Apply feature flags (emotion, voice_design, scene_context) by reading from
   TTSOrchestrator constants.
3. Gate optional parameters based on enabled flags:
   - emotion: only pass if EMOTION_ENABLED
   - voice_stability, voice_style, voice_speed: only pass if VOICE_DESIGN_ENABLED
"""
from pathlib import Path

from src.domain.models import Segment
from src.tts.segment_context_resolver import SegmentContext
from src.tts.tts_provider import TTSProvider


class SegmentSynthesizer:
    """Owns provider calls and feature flag gating for individual segments."""

    def __init__(self, provider: TTSProvider) -> None:
        """Initialize with a TTS provider.

        Args:
            provider: TTSProvider instance for synthesizing audio.
        """
        self._provider = provider

    def synthesize_segment(
        self,
        segment: Segment,
        voice_id: str,
        output_path: Path,
        context: SegmentContext,
    ) -> str | None:
        """Synthesize one segment with feature flags applied.

        Applies feature flags by reading from TTSOrchestrator constants:
        - EMOTION_ENABLED: gates segment.emotion
        - VOICE_DESIGN_ENABLED: gates voice_stability, voice_style, voice_speed

        Args:
            segment: Segment to synthesize.
            voice_id: Voice ID to use.
            output_path: Path to write MP3 to.
            context: SegmentContext with continuity and voice modifiers.

        Returns:
            request_id from provider, or None if not available.
        """
        # Import here to avoid circular dependency and to allow tests to patch
        from src.tts.tts_orchestrator import TTSOrchestrator

        # Apply feature flags
        emotion = (
            segment.emotion if TTSOrchestrator.EMOTION_ENABLED else None
        )
        voice_stability = (
            context.voice_stability
            if TTSOrchestrator.VOICE_DESIGN_ENABLED
            else None
        )
        voice_style = (
            context.voice_style
            if TTSOrchestrator.VOICE_DESIGN_ENABLED
            else None
        )
        voice_speed = (
            context.voice_speed
            if TTSOrchestrator.VOICE_DESIGN_ENABLED
            else None
        )

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
