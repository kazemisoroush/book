"""Tests for ElevenLabsSoundEffectProvider."""
import hashlib
from pathlib import Path

from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)


class MockElevenLabsClient:
    """Mock ElevenLabs client for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.call_count = 0
        self.last_description: str | None = None
        self.last_duration: float | None = None
        self.text_to_sound_effects = self

    def convert(self, text: str, duration_seconds: float) -> list[bytes]:
        """Mock convert method."""
        self.call_count += 1
        self.last_description = text
        self.last_duration = duration_seconds
        if self.should_fail:
            raise RuntimeError("API failure")
        return [b"fake", b"audio", b"data"]


class TestElevenLabsSoundEffectProvider:
    """Test ElevenLabs sound effect provider implementation."""

    def test_generate_calls_api_and_caches_result(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        output_path = tmp_path / "output.mp3"

        # Act
        result = provider.generate("door knock", output_path, duration_seconds=3.0)

        # Assert
        assert result == output_path
        assert output_path.exists()
        assert client.call_count == 1
        assert client.last_description == "door knock"
        assert client.last_duration == 3.0

    def test_cache_hit_skips_api_call(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        output_path = tmp_path / "output.mp3"

        # Generate once
        provider.generate("door knock", output_path)

        # Act - second call with same description
        result = provider.generate("door knock", output_path)

        # Assert
        assert result == output_path
        assert client.call_count == 1  # Only called once

    def test_api_failure_returns_none(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient(should_fail=True)
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        output_path = tmp_path / "output.mp3"

        # Act
        result = provider.generate("door knock", output_path)

        # Assert
        assert result is None
        assert not output_path.exists()

    def test_cache_key_is_hash_of_description(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        description = "door knock"
        expected_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
        expected_cache_path = tmp_path / f"{expected_hash}.mp3"
        output_path = tmp_path / "output.mp3"

        # Act
        result = provider.generate(description, output_path)

        # Assert - should have created cache file with hash name
        assert expected_cache_path.exists()
        assert result == output_path
