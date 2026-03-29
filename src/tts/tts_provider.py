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
