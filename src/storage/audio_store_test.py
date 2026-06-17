"""Unit tests for AudioStore key layout."""
from pathlib import Path

from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage


def _store(tmp_path: Path) -> AudioStore:
    return AudioStore(LocalStorage(tmp_path))


class TestKeys:
    """Key shapes match the on-disk layout the pipeline expects."""

    def test_tts_beat_key(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act
        key = store.tts_beat_key("alice", "elevenlabs_v2", 7)

        # Assert
        assert key == "alice/audio/tts/elevenlabs_v2/beat_0007.mp3"

    def test_tts_chunk_key(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act
        key = store.tts_chunk_key(
            "alice", "elevenlabs_dialogue", "chapter_003", 12,
        )

        # Assert
        assert key == "alice/audio/tts/elevenlabs_dialogue/chapter_003/chunk_0012.mp3"

    def test_sfx_beat_key_default_extension(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act / Assert
        assert store.sfx_beat_key("alice", "elevenlabs", 2) == (
            "alice/audio/sfx/elevenlabs/beat_0002.mp3"
        )

    def test_sfx_beat_key_wav_extension(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act / Assert
        assert store.sfx_beat_key("alice", "audiogen", 3, extension="wav") == (
            "alice/audio/sfx/audiogen/beat_0003.wav"
        )

    def test_silence_clip_key(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act / Assert
        assert store.silence_clip_key("alice", "elevenlabs_v2", 1000) == (
            "alice/audio/tts/elevenlabs_v2/silence_1000ms.mp3"
        )

    def test_mix_output_key(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act / Assert
        assert store.mix_output_key("alice", "fish_audio", "chapter_001") == (
            "alice/audio/mix/fish_audio/chapter_001.mp3"
        )


class TestPassThroughOps:
    """AudioStore delegates bytes/text IO to its underlying Storage."""

    def test_write_and_read_bytes(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        key = store.tts_beat_key("alice", "fish_audio", 1)

        # Act
        store.write_bytes(key, b"audio")

        # Assert
        assert store.read_bytes(key) == b"audio"
        assert store.exists(key) is True

    def test_local_path_yields_a_real_path(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        key = store.tts_beat_key("alice", "elevenlabs_v2", 1)

        # Act
        with store.local_path(key, "w") as path:
            path.write_bytes(b"clip")

        # Assert
        assert store.read_bytes(key) == b"clip"


class TestIterChunkKeys:
    """iter_chunk_keys lists dialogue chunks in sorted order."""

    def test_returns_chunks_only(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        store.write_bytes(store.tts_chunk_key("alice", "elevenlabs_dialogue", "chapter_001", 2), b"x")
        store.write_bytes(store.tts_chunk_key("alice", "elevenlabs_dialogue", "chapter_001", 1), b"y")
        store.write_text(
            "alice/audio/tts/elevenlabs_dialogue/chapter_001/notes.txt",
            "irrelevant",
        )

        # Act
        keys = list(store.iter_chunk_keys("alice", "elevenlabs_dialogue", "chapter_001"))

        # Assert
        assert keys == [
            "alice/audio/tts/elevenlabs_dialogue/chapter_001/chunk_0001.mp3",
            "alice/audio/tts/elevenlabs_dialogue/chapter_001/chunk_0002.mp3",
        ]
