"""Tests for TTSProvider interface."""
from pathlib import Path
from typing import Any, Optional

import pytest

from src.audio.tts.tts_provider import StubTTSProvider, TTSProvider
from src.audio.tts.voice_assigner import VoiceEntry


class MinimalTTSProvider(TTSProvider):
    """Minimal concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "minimal"

    def provide(self, beat: object, voice_id: str, book_id: str) -> float:
        return 0.0

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
        """Minimal implementation."""
        return None

    def get_available_voices(self) -> dict[str, str]:
        """Minimal implementation."""
        return {}

    def get_voices(self) -> list[dict[str, Any]]:
        """Minimal implementation."""
        return []


class TestTTSProviderNameProperty:
    """Tests for the abstract name property on TTSProvider."""

    def test_name_is_abstract(self) -> None:
        """Implementing TTSProvider without name raises TypeError."""
        # Arrange & Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class NoNameProvider(TTSProvider):
                def provide(self, beat: object, voice_id: str, book_id: str) -> float:
                    return 0.0

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
                    return None

                def get_available_voices(self) -> dict[str, str]:
                    return {}

                def get_voices(self) -> list[dict[str, Any]]:
                    return []

                # Missing name property

            NoNameProvider()  # type: ignore[abstract]

    def test_stub_provider_name(self) -> None:
        """StubTTSProvider.name returns 'stub'."""
        # Arrange
        stub = StubTTSProvider([VoiceEntry(voice_id="v1", name="V", labels={})])

        # Act & Assert
        assert stub.name == "stub"


class TestTTSProviderGetVoicesAbstractMethod:
    """Tests for get_voices() abstract method."""

    def test_get_voices_is_abstract(self) -> None:
        """Attempting to instantiate TTSProvider without get_voices() must fail."""
        # Arrange & Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class IncompleteProvider(TTSProvider):
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
                    return None

                def get_available_voices(self) -> dict[str, str]:
                    return {}

                # Missing get_voices()

            IncompleteProvider()  # type: ignore[abstract]

    def test_get_voices_returns_list_of_dicts(self) -> None:
        """get_voices() must return a list of dictionaries."""
        # Arrange
        provider = MinimalTTSProvider()

        # Act
        result = provider.get_voices()

        # Assert
        assert isinstance(result, list)


class TestStubTTSProvider:
    """Tests for StubTTSProvider — test helper that wraps a pre-built VoiceEntry list."""

    def test_get_voices_returns_voices_as_dicts(self) -> None:
        """StubTTSProvider.get_voices() returns the voices passed at construction as dicts."""
        # Arrange
        entries = [
            VoiceEntry(voice_id="v1", name="Alice", labels={"gender": "female"}),
            VoiceEntry(voice_id="v2", name="Bob", labels={"gender": "male"}),
        ]
        stub = StubTTSProvider(entries)

        # Act
        result = stub.get_voices()

        # Assert
        assert len(result) == 2
        assert result[0]["voice_id"] == "v1"
        assert result[0]["name"] == "Alice"
        assert result[0]["labels"] == {"gender": "female"}
        assert result[1]["voice_id"] == "v2"

    def test_synthesize_raises_not_implemented(self) -> None:
        """StubTTSProvider.synthesize() raises NotImplementedError."""
        # Arrange
        stub = StubTTSProvider([VoiceEntry(voice_id="v1", name="V", labels={})])

        # Act & Assert
        with pytest.raises(NotImplementedError):
            stub.synthesize("hello", "v1", Path("/tmp/out.mp3"))

    def test_get_available_voices_raises_not_implemented(self) -> None:
        """StubTTSProvider.get_available_voices() raises NotImplementedError."""
        # Arrange
        stub = StubTTSProvider([VoiceEntry(voice_id="v1", name="V", labels={})])

        # Act & Assert
        with pytest.raises(NotImplementedError):
            stub.get_available_voices()
