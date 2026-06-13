"""Interface for TTS providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.domain.beat import Beat

if TYPE_CHECKING:
    from src.audio.tts.beat_context_resolver import BeatContext


class TTSProvider(ABC):
    """Renders text to audio for a given voice token."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for namespacing cached audio on disk."""

    @abstractmethod
    def provide(
        self,
        beat: Beat,
        voice_id: str,
        book_id: str,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        """Synthesise *beat* with *voice_id* under *book_id* and return the request id."""

    @abstractmethod
    def synthesize(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        """Synthesise *beat* to *output_path* and return the request id."""


class StubTTSProvider(TTSProvider):
    """Test helper that counts ``provide`` calls and records context."""

    @property
    def name(self) -> str:
        return "stub"

    def __init__(self) -> None:
        self._provide_call_count = 0
        self.last_voice_id: Optional[str] = None
        self.provide_contexts: list[Optional["BeatContext"]] = []

    def provide(
        self,
        beat: Beat,
        voice_id: str,
        book_id: str,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        self._provide_call_count += 1
        self.last_voice_id = voice_id
        self.provide_contexts.append(context)
        return f"stub-req-{self._provide_call_count:04d}"

    def synthesize(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        raise NotImplementedError("StubTTSProvider does not support synthesis")
