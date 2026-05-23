"""Tests for ElevenLabsAmbientProvider."""
from pathlib import Path

from src.audio.ambient.elevenlabs_ambient_provider import ElevenLabsAmbientProvider
from src.domain.models import Scene


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


class TestElevenLabsAmbientProviderName:
    def test_name_returns_elevenlabs(self, tmp_path: Path) -> None:
        provider = ElevenLabsAmbientProvider(MockElevenLabsClient(), tmp_path)
        assert provider.name == "elevenlabs"


class TestElevenLabsAmbientProviderGenerate:
    """Internal _generate helper still used by AudioOrchestrator."""

    def test_generate_calls_api_with_loop_enabled(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        output_path = tmp_path / "scene_123.mp3"

        result = provider._generate(
            "forest ambience", output_path, duration_seconds=30.0
        )

        assert result == output_path
        assert output_path.exists()
        assert client.call_count == 1
        assert client.last_prompt == "forest ambience"
        assert client.last_duration == 30.0
        assert client.last_loop is True

    def test_cache_hit_skips_api_call(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        output_path = tmp_path / "scene_123.mp3"

        provider._generate("forest ambience", output_path)
        result = provider._generate("forest ambience", output_path)

        assert result == output_path
        assert client.call_count == 1

    def test_api_failure_returns_none(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient(should_fail=True)
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        output_path = tmp_path / "scene_123.mp3"

        result = provider._generate("forest ambience", output_path)

        assert result is None
        assert not output_path.exists()


class TestElevenLabsAmbientProviderProvide:
    """provide(scene, book_id) derives a per-book path from scene.scene_id."""

    def test_writes_to_per_book_path(self, tmp_path: Path, monkeypatch) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        scene = Scene(
            scene_id="living_room",
            environment="cozy living room",
            ambient_prompt="crackling fire",
        )
        # Stub duration to avoid mutagen on fake bytes
        monkeypatch.setattr(
            "src.audio.ambient.elevenlabs_ambient_provider._audio_duration_seconds",
            lambda _path: 42.0,
        )

        duration = provider.provide(scene, "pride_and_prejudice")

        expected = (
            tmp_path / "pride_and_prejudice" / "audio" / "ambient" / "elevenlabs"
            / "living_room.mp3"
        )
        assert expected.exists()
        assert duration == 42.0
        assert client.last_prompt == "crackling fire"
        assert client.last_loop is True

    def test_cache_hit_skips_second_api_call(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsAmbientProvider(client, tmp_path)
        scene = Scene(
            scene_id="living_room",
            environment="cozy living room",
            ambient_prompt="crackling fire",
        )
        monkeypatch.setattr(
            "src.audio.ambient.elevenlabs_ambient_provider._audio_duration_seconds",
            lambda _path: 1.0,
        )

        provider.provide(scene, "pride_and_prejudice")
        provider.provide(scene, "pride_and_prejudice")

        assert client.call_count == 1

    def test_raises_when_scene_has_no_ambient_prompt(self, tmp_path: Path) -> None:
        provider = ElevenLabsAmbientProvider(MockElevenLabsClient(), tmp_path)
        scene = Scene(scene_id="silent_room", environment="empty")

        import pytest
        with pytest.raises(ValueError, match="ambient_prompt"):
            provider.provide(scene, "any_book")
