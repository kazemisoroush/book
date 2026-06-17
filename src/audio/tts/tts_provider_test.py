"""Tests for TTSProvider interface."""
from typing import Optional

import pytest

from src.audio.tts.tts_provider import StubTTSProvider, TTSProvider
from src.domain.beat import Beat, BeatType
from src.domain.models import Chapter


class _RecordingProvider(TTSProvider):
    """Concrete TTSProvider that only implements provide; uses default provide_collection."""

    @property
    def name(self) -> str:
        return "recording"

    def __init__(self) -> None:
        self.calls: list[Beat] = []

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        self.calls.append(beat)
        return f"req-{len(self.calls)}"


class TestTTSProviderNameProperty:
    """The name property is abstract."""

    def test_name_is_abstract(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class NoNameProvider(TTSProvider):
                def provide(self, beat: Beat, book_id: str) -> Optional[str]:
                    return None

            NoNameProvider()  # type: ignore[abstract]


class TestStubTTSProvider:
    """StubTTSProvider records every call for assertions."""

    def test_provide_records_each_beat(self) -> None:
        # Arrange
        stub = StubTTSProvider()
        beat = Beat(text="hi", beat_type=BeatType.NARRATION, character_id=1, voice_id="v1")

        # Act
        stub.provide(beat, "book")
        stub.provide(beat, "book")

        # Assert
        assert len(stub.provide_calls) == 2
        assert stub.provide_calls[0] is beat


class TestProvideCollectionDefault:
    """The default provide_collection loops over provide in order."""

    def test_default_returns_one_request_id_per_beat(self) -> None:
        # Arrange
        provider = _RecordingProvider()
        beats = [
            Beat(text="a", beat_type=BeatType.NARRATION, character_id=1, voice_id="v1"),
            Beat(text="b", beat_type=BeatType.DIALOGUE, character_id=2, voice_id="v2"),
        ]

        # Act
        ids = provider.provide_collection(
            Chapter(number=1, title="", beats=beats), book_id="book",
        )

        # Assert
        assert ids == ["req-1", "req-2"]
        assert [b.text for b in provider.calls] == ["a", "b"]
