"""Interface for TTS providers."""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.beat import Beat


class TTSProvider(ABC):
    """Renders beats to audio."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for namespacing cached audio on disk."""

    @abstractmethod
    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise one *beat* and return the request id."""

    def provide_collection(
        self, beats: list[Beat], book_id: str,
    ) -> list[Optional[str]]:
        """Synthesise an ordered *beats* batch and return the request ids."""
        return [self.provide(beat, book_id) for beat in beats]


class StubTTSProvider(TTSProvider):
    """Test helper that records every provide call."""

    @property
    def name(self) -> str:
        return "stub"

    def __init__(self) -> None:
        self.provide_calls: list[Beat] = []
        self.collection_calls: list[list[Beat]] = []

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        self.provide_calls.append(beat)
        return f"stub-req-{len(self.provide_calls):04d}"

    def provide_collection(
        self, beats: list[Beat], book_id: str,
    ) -> list[Optional[str]]:
        self.collection_calls.append(list(beats))
        return [self.provide(beat, book_id) for beat in beats]
