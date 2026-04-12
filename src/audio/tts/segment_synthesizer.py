"""SegmentSynthesizer — provider calls for individual segments.

Responsibilities
----------------
1. Call the injected TTSProvider for each segment.
2. Pass all segment attributes (emotion, voice design) through to the provider.

The synthesizer is "dumb" — it does not gate any fields. Feature flags are
enforced upstream in the PromptBuilder, which controls what the LLM emits.
"""
from pathlib import Path

from src.domain.models import Segment
from src.audio.tts.segment_context_resolver import SegmentContext
from src.audio.tts.tts_provider import TTSProvider


class SegmentSynthesizer:
    """Owns provider calls for individual segments — passes everything through."""

    def __init__(
        self,
        provider: TTSProvider,
    ) -> None:
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
        """Synthesize one segment, passing all attributes through to the provider.

        Args:
            segment: Segment to synthesize.
            voice_id: Voice ID to use.
            output_path: Path to write MP3 to.
            context: SegmentContext with continuity and voice modifiers.

        Returns:
            request_id from provider, or None if not available.
        """
        return self._provider.synthesize(
            segment.text,
            voice_id,
            output_path,
            emotion=segment.emotion,
            previous_text=context.previous_text,
            next_text=context.next_text,
            voice_stability=context.voice_stability,
            voice_style=context.voice_style,
            voice_speed=context.voice_speed,
            previous_request_ids=context.previous_request_ids,
        )
