"""Interface for TTS providers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


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
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
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
            previous_request_ids: Optional list of up to 3 request IDs from
                                  prior same-voice synthesis calls.  Provides
                                  acoustic continuity — the model matches
                                  pitch, speaking rate, and energy.

        Returns:
            The request ID from the API response, or None if not available.
            Callers can pass returned IDs as ``previous_request_ids`` on
            subsequent same-voice calls for acoustic continuity.
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

    @abstractmethod
    def get_voices(self) -> list[dict[str, Any]]:
        """
        Get available voices with full metadata.

        Returns:
            List of voice dictionaries, each containing at least:
            - voice_id: str — unique voice identifier
            - name: str — human-readable voice name
            - labels: dict[str, str] — voice metadata tags (e.g. gender, age)
        """
        pass
