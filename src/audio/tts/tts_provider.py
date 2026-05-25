"""Interface for TTS providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.domain.beat import Beat


class TTSProvider(ABC):
    """Abstract base class for TTS providers.

    A TTS provider only knows how to render text to audio for a given
    voice token. It does not own the voice catalogue or the lifecycle of
    voices; that responsibility lives on :class:`CharacterProvider`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this provider (e.g. ``"elevenlabs"``).

        Used to namespace cached artifacts on disk so that switching providers
        never silently serves stale audio from a different provider.
        """

    @abstractmethod
    def provide(self, beat: Beat, voice_id: str, book_id: str) -> None:
        """Synthesize speech for a beat.

        Constructs the output path, creates directories, and calls synthesize().

        Args:
            beat: The beat to synthesize.
            voice_id: The voice identifier to use.
            book_id: The book identifier (used for output path construction).
        """

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
        """Synthesize text to speech.

        Args:
            text: The text to synthesize
            voice_id: The voice identifier to use
            output_path: Where to save the audio file
            emotion: Optional emotion tag (e.g. "ANGRY", "STERN"). When
                provided and not "NEUTRAL", implementations may adjust
                synthesis settings or prepend inline audio tags.
            previous_text: Optional text that precedes this beat. Helps
                the TTS model match prosody to what came before.
            next_text: Optional text that follows this beat. Helps the
                TTS model know how to end the beat naturally.
            voice_stability: Optional stability value (0.0-1.0) from the LLM.
                When provided, overrides the binary preset.
            voice_style: Optional style value (0.0-1.0) from the LLM.
                When provided, overrides the binary preset.
            voice_speed: Optional speed value from the LLM (e.g. 0.90-1.10).
            previous_request_ids: Optional list of up to 3 request IDs from
                prior same-voice synthesis calls. Provides acoustic
                continuity ; the model matches pitch, speaking rate, and energy.

        Returns:
            The request ID from the API response, or None if not available.
            Callers can pass returned IDs as ``previous_request_ids`` on
            subsequent same-voice calls for acoustic continuity.
        """


class StubTTSProvider(TTSProvider):
    """Test helper that counts ``provide`` calls and does no synthesis."""

    @property
    def name(self) -> str:
        return "stub"

    def __init__(self) -> None:
        self._provide_call_count = 0
        self.last_voice_id: Optional[str] = None

    def provide(self, beat: Beat, voice_id: str, book_id: str) -> None:
        self._provide_call_count += 1
        self.last_voice_id = voice_id

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
        raise NotImplementedError("StubTTSProvider does not support synthesis")
