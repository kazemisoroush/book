"""Interface for TTS providers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
    ) -> None:
        """
        Synthesize text to speech.

        Args:
            text: The text to synthesize
            voice_id: The voice identifier to use
            output_path: Where to save the audio file
            emotion: Optional emotion tag (e.g. "ANGRY", "STERN").  When
                     provided and not "NEUTRAL", implementations may adjust
                     synthesis settings or prepend inline audio tags.
            previous_text: Optional text that precedes this segment.  Helps
                           the TTS model match prosody to what came before.
            next_text: Optional text that follows this segment.  Helps the
                       TTS model know how to end the segment naturally.
            voice_stability: Optional stability value (0.0–1.0) from the LLM.
                             When provided, overrides the binary preset.
            voice_style: Optional style value (0.0–1.0) from the LLM.
                         When provided, overrides the binary preset.
            voice_speed: Optional speed value from the LLM (e.g. 0.90–1.10).
                         Reserved for future use.
        """
        pass

    @abstractmethod
    def get_available_voices(self) -> dict[str, str]:
        """
        Get available voices.

        Returns:
            Dictionary mapping voice names to voice IDs
        """
        pass
