"""Tests for ElevenLabsSoundEffectProvider."""
from pathlib import Path

from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.domain.beat import Beat, BeatType


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
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        output_path = tmp_path / "output.mp3"

        result = provider._generate("door knock", output_path, duration_seconds=3.0)

        assert result == output_path
        assert output_path.exists()
        assert client.call_count == 1
        assert client.last_description == "door knock"
        assert client.last_duration == 3.0

    def test_cache_hit_skips_api_call(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        output_path = tmp_path / "output.mp3"

        provider._generate("door knock", output_path)
        provider._generate("door knock", output_path)

        assert client.call_count == 1

    def test_api_failure_returns_none(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient(should_fail=True)
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        output_path = tmp_path / "output.mp3"

        result = provider._generate("door knock", output_path)

        assert result is None
        assert not output_path.exists()


class TestElevenLabsSoundEffectProviderProvide:
    """provide(beat, book_id) derives a per-book path with a beat counter."""

    def test_writes_to_per_book_path(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)
        beat = Beat(
            text="firm knock on a wooden door",
            beat_type=BeatType.SOUND_EFFECT,
        )

        provider.provide(beat, "pride_and_prejudice")

        expected = (
            tmp_path / "pride_and_prejudice" / "audio" / "sfx" / "elevenlabs"
            / "beat_0001.mp3"
        )
        assert expected.exists()
        assert client.last_description == "firm knock on a wooden door"

    def test_counter_increments_per_beat(self, tmp_path: Path) -> None:
        client = MockElevenLabsClient()
        provider = ElevenLabsSoundEffectProvider(client, tmp_path)

        beat_one = Beat(text="d1", beat_type=BeatType.SOUND_EFFECT)
        beat_two = Beat(text="d2", beat_type=BeatType.SOUND_EFFECT)
        provider.provide(beat_one, "book")
        provider.provide(beat_two, "book")

        first = (
            tmp_path / "book" / "audio" / "sfx" / "elevenlabs" / "beat_0001.mp3"
        )
        second = (
            tmp_path / "book" / "audio" / "sfx" / "elevenlabs" / "beat_0002.mp3"
        )
        assert first.exists()
        assert second.exists()
