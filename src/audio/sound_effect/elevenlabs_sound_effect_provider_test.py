"""Tests for ElevenLabsSoundEffectProvider."""
from pathlib import Path

from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.domain.beat import Beat, BeatType
from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage
from src.storage.objects import SFXBeatRef


def _audio_store(tmp_path: Path) -> AudioStore:
    return AudioStore(LocalStorage(tmp_path))


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


class TestElevenLabsSoundEffectProviderGenerate:
    """Internal _generate helper used by SfxWorkflow."""

    def test_generate_calls_api(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, _audio_store(tmp_path))
        ref = SFXBeatRef("book", "elevenlabs", 1)

        # Act
        ok = provider._generate("door knock", ref, duration_seconds=3.0)

        # Assert
        assert ok is True
        assert (
            tmp_path / "book" / "audio" / "sfx" / "elevenlabs" / "beat_0001.mp3"
        ).exists()
        assert client.call_count == 1
        assert client.last_description == "door knock"
        assert client.last_duration == 3.0

    def test_cache_hit_skips_api_call(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, _audio_store(tmp_path))
        ref = SFXBeatRef("book", "elevenlabs", 1)

        # Act
        provider._generate("door knock", ref)
        provider._generate("door knock", ref)

        # Assert
        assert client.call_count == 1

    def test_api_failure_returns_false(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient(should_fail=True)
        provider = ElevenLabsSoundEffectProvider(client, _audio_store(tmp_path))
        ref = SFXBeatRef("book", "elevenlabs", 1)

        # Act
        ok = provider._generate("door knock", ref)

        # Assert
        assert ok is False
        assert not (
            tmp_path / "book" / "audio" / "sfx" / "elevenlabs" / "beat_0001.mp3"
        ).exists()


class TestElevenLabsSoundEffectProviderProvide:
    """provide(beat, book_id) derives a per-book ref with a beat counter."""

    def test_writes_to_per_book_path(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, _audio_store(tmp_path))
        beat = Beat(
            text="firm knock on a wooden door",
            beat_type=BeatType.SOUND_EFFECT,
        )

        # Act
        provider.provide(beat, "pride_and_prejudice")

        # Assert
        expected = (
            tmp_path / "pride_and_prejudice" / "audio" / "sfx" / "elevenlabs"
            / "beat_0001.mp3"
        )
        assert expected.exists()
        assert client.last_description == "firm knock on a wooden door"

    def test_counter_increments_per_beat(self, tmp_path: Path) -> None:
        # Arrange
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, _audio_store(tmp_path))

        # Act
        provider.provide(Beat(text="d1", beat_type=BeatType.SOUND_EFFECT), "book")
        provider.provide(Beat(text="d2", beat_type=BeatType.SOUND_EFFECT), "book")

        # Assert
        first = tmp_path / "book" / "audio" / "sfx" / "elevenlabs" / "beat_0001.mp3"
        second = tmp_path / "book" / "audio" / "sfx" / "elevenlabs" / "beat_0002.mp3"
        assert first.exists()
        assert second.exists()
