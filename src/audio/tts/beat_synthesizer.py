"""BeatSynthesizer — provider calls for individual beats.

Responsibilities
----------------
1. Call the injected TTSProvider for each beat.
2. Pass all beat attributes (emotion, voice design) through to the provider.

The synthesizer is "dumb" — it does not gate any fields. Feature flags are
enforced upstream in the PromptBuilder, which controls what the LLM emits.
"""
from pathlib import Path

from src.audio.tts.beat_context_resolver import BeatContext
from src.audio.tts.tts_provider import TTSProvider
from src.domain.models import Beat


class BeatSynthesizer:
    """Owns provider calls for individual beats — passes everything through."""

    def __init__(
        self,
        provider: TTSProvider,
    ) -> None:
        """Initialize with a TTS provider.

        Args:
            provider: TTSProvider instance for synthesizing audio.
        """
        self._provider = provider

    def synthesize_beat(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
        context: BeatContext,
    ) -> str | None:
        """Synthesize one beat, passing all attributes through to the provider.

        Args:
            beat: Beat to synthesize.
            voice_id: Voice ID to use.
            output_path: Path to write MP3 to.
            context: BeatContext with continuity and voice modifiers.

        Returns:
            request_id from provider, or None if not available.
        """
        return self._provider.synthesize(
            beat.text,
            voice_id,
            output_path,
            emotion=beat.emotion,
            previous_text=context.previous_text,
            next_text=context.next_text,
            voice_stability=context.voice_stability,
            voice_style=context.voice_style,
            voice_speed=context.voice_speed,
            previous_request_ids=context.previous_request_ids,
        )
