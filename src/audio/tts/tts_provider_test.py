"""Tests for TTSProvider interface."""
from pathlib import Path
from typing import Optional

import pytest

from src.audio.tts.beat_context_resolver import BeatContext
from src.audio.tts.tts_provider import StubTTSProvider, TTSProvider
from src.domain.beat import Beat, BeatType


class MinimalTTSProvider(TTSProvider):
    """Minimal concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "minimal"

    def provide(
        self,
        beat: Beat,
        voice_id: str,
        book_id: str,
        context: Optional[BeatContext] = None,
    ) -> Optional[str]:
        return None

    def synthesize(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
        context: Optional[BeatContext] = None,
    ) -> Optional[str]:
        return None


class TestTTSProviderNameProperty:
    """Tests for the abstract name property on TTSProvider."""

    def test_name_is_abstract(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class NoNameProvider(TTSProvider):
                def provide(
                    self,
                    beat: Beat,
                    voice_id: str,
                    book_id: str,
                    context: Optional[BeatContext] = None,
                ) -> Optional[str]:
                    return None

                def synthesize(
                    self,
                    beat: Beat,
                    voice_id: str,
                    output_path: Path,
                    context: Optional[BeatContext] = None,
                ) -> Optional[str]:
                    return None

            NoNameProvider()  # type: ignore[abstract]

    def test_stub_provider_name(self) -> None:
        # Arrange
        stub = StubTTSProvider()

        # Act / Assert
        assert stub.name == "stub"


class TestStubTTSProvider:
    """Tests for StubTTSProvider."""

    def test_provide_counts_calls(self) -> None:
        # Arrange
        stub = StubTTSProvider()
        beat = Beat(text="hi", beat_type=BeatType.NARRATION, character_id=1)

        # Act
        stub.provide(beat, "v1", "book")
        stub.provide(beat, "v2", "book")

        # Assert
        assert stub._provide_call_count == 2
        assert stub.last_voice_id == "v2"

    def test_synthesize_raises_not_implemented(self) -> None:
        # Arrange
        stub = StubTTSProvider()
        beat = Beat(text="hello", beat_type=BeatType.NARRATION)

        # Act / Assert
        with pytest.raises(NotImplementedError):
            stub.synthesize(beat, "v1", Path("/tmp/out.mp3"))
