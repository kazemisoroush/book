"""Interface for TTS providers."""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.beat import Beat
from src.domain.models import Chapter


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
        self, chapter: Chapter, book_id: str,
    ) -> list[Optional[str]]:
        """Synthesise *chapter* and return the request ids in beat order."""
        return [self.provide(beat, book_id) for beat in chapter.beats]


class StubTTSProvider(TTSProvider):
    """Test helper that records every provide call."""

    @property
    def name(self) -> str:
        return "stub"

    def __init__(self) -> None:
        self.provide_calls: list[Beat] = []
        self.collection_calls: list[Chapter] = []

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        self.provide_calls.append(beat)
        return f"stub-req-{len(self.provide_calls):04d}"

    def provide_collection(
        self, chapter: Chapter, book_id: str,
    ) -> list[Optional[str]]:
        self.collection_calls.append(chapter)
        return [self.provide(beat, book_id) for beat in chapter.beats]
