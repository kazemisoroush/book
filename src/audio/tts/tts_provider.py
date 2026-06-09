"""Interface for TTS providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.domain.beat import Beat


class TTSProvider(ABC):
    """Renders text to audio for a given voice token."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for namespacing cached audio on disk."""

    @abstractmethod
    def provide(self, beat: Beat, voice_id: str, book_id: str) -> None:
        """Synthesise *beat* with *voice_id* under *book_id*."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesise *text* to *output_path* and return the request id."""


class StubTTSProvider(TTSProvider):
    """Test helper that counts ``provide`` calls."""

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
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        raise NotImplementedError("StubTTSProvider does not support synthesis")
