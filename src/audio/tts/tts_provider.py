"""Interface for TTS providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from src.domain.models import Segment


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def provide(self, segment: Segment, voice_id: str, book_id: str) -> float:
        """Synthesize speech for a segment.

        Constructs the output path, creates directories, calls synthesize(),
        measures duration, and sets ``segment.audio_path``.

        Args:
            segment: The segment to synthesize.
            voice_id: The voice identifier to use.
            book_id: The book identifier (used for output path construction).

        Returns:
            Duration of the generated audio in seconds.
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


class StubTTSProvider(TTSProvider):
    """Test helper that wraps a pre-built list of ``VoiceEntry`` objects as a ``TTSProvider``.

    Accepts a list of ``VoiceEntry`` at construction and returns them as
    plain dicts from :meth:`get_voices`.  :meth:`provide` sets
    ``segment.audio_path`` to a deterministic path and returns a fixed
    duration (1.0s by default).

    Usage::

        from src.audio.tts.tts_provider import StubTTSProvider
        from src.audio.tts.voice_assigner import VoiceAssigner, VoiceEntry

        voices = [VoiceEntry(voice_id="v1", name="Alice", labels={"gender": "female"})]
        assigner = VoiceAssigner(StubTTSProvider(voices))
        assignment = assigner.assign(registry)
    """

    def __init__(self, voices: list[Any], fixed_duration: float = 1.0) -> None:
        """Initialise with a list of :class:`VoiceEntry` objects.

        Args:
            voices: List of ``VoiceEntry`` objects whose fields (``voice_id``,
                    ``name``, ``labels``) will be returned by :meth:`get_voices`.
            fixed_duration: Duration returned by :meth:`provide` (default 1.0).
        """
        self._entries = list(voices)
        self._fixed_duration = fixed_duration
        self._provide_call_count = 0

    def provide(self, segment: Segment, voice_id: str, book_id: str) -> float:
        """Set segment.audio_path to a deterministic path and return fixed duration."""
        self._provide_call_count += 1
        segment.audio_path = f"books/{book_id}/audio/tts/seg_{self._provide_call_count:04d}.mp3"
        return self._fixed_duration

    def get_voices(self) -> list[dict[str, Any]]:
        """Return the pre-built voice entries as plain dicts."""
        return [
            {
                "voice_id": e.voice_id,
                "name": e.name,
                "labels": e.labels,
            }
            for e in self._entries
        ]

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
        """Not implemented — this stub is for voice listing only."""
        raise NotImplementedError("StubTTSProvider does not support synthesis")

    def get_available_voices(self) -> dict[str, str]:
        """Not implemented — this stub is for voice listing only."""
        raise NotImplementedError("StubTTSProvider does not support get_available_voices")
