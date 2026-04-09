"""Tests for ElevenLabsAmbientProvider."""
from pathlib import Path

from src.tts.elevenlabs_ambient_provider import ElevenLabsAmbientProvider


class MockElevenLabsClient:
    """Mock ElevenLabs client for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.call_count = 0
        self.last_prompt: str | None = None
        self.last_duration: float | None = None
        self.last_loop: bool | None = None
        self.text_to_sound_effects = self

    def convert(
        self, text: str, duration_seconds: float, loop: bool = False
    ) -> list[bytes]:
        """Mock convert method."""
        self.call_count += 1
        self.last_prompt = text
        self.last_duration = duration_seconds
        self.last_loop = loop
        if self.should_fail:
            raise RuntimeError("API failure")
        return [b"fake", b"ambient", b"data"]


class TestElevenLabsAmbientProvider:
    """Test ElevenLabs ambient provider implementation."""

    def test_implements_interface(self) -> None:
        # Arrange
        client = MockElevenLabsClient()
        cache_dir = Path("/tmp/ambient_cache")

        # Act
        provider = ElevenLabsAmbientProvider(client, cache_dir)

        # Assert
        assert provider is not None

    def test_generate_calls_api_with_loop_enabled(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        output_path = tmp_path / "scene_123.mp3"

        # Act
        result = provider.generate(
            "forest ambience", output_path, duration_seconds=30.0
        )

        # Assert
        assert result == output_path
        assert output_path.exists()
        assert client.call_count == 1
        assert client.last_prompt == "forest ambience"
        assert client.last_duration == 30.0
        assert client.last_loop is True

    def test_cache_hit_skips_api_call(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        output_path = tmp_path / "scene_123.mp3"

        # Generate once
        provider.generate("forest ambience", output_path)

        # Act - second call with same output_path
        result = provider.generate("forest ambience", output_path)

        # Assert
        assert result == output_path
        assert client.call_count == 1  # Only called once

    def test_api_failure_returns_none(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient(should_fail=True)
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        output_path = tmp_path / "scene_123.mp3"

        # Act
        result = provider.generate("forest ambience", output_path)

        # Assert
        assert result is None
        assert not output_path.exists()

    def test_cache_key_is_output_path_name(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        # Using scene_id as filename (as per spec)
        output_path = tmp_path / "scene_forest_001.mp3"

        # Act
        result = provider.generate("forest ambience", output_path)

        # Assert - cache file should match output_path name
        cache_path = tmp_path / "scene_forest_001.mp3"
        assert cache_path.exists()
        assert result == output_path
