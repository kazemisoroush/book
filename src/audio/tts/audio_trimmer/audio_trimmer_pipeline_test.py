"""Tests for AudioTrimmerPipeline."""
from pathlib import Path

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer
from src.audio.tts.audio_trimmer.audio_trimmer_pipeline import AudioTrimmerPipeline
from src.domain.beat import Beat, BeatType
from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage
from src.storage.objects import TTSBeat, TTSBeatRef


class _RecordingTrimmer(AudioTrimmer):
    """Touch the output file and record the (input, output) pair."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path]] = []

    def _trim(self, input_path: Path, output_path: Path) -> Path:
        self.calls.append((input_path, output_path))
        output_path.write_bytes(b"\x00" * 8)
        return output_path


def _audio_store(tmp_path: Path) -> AudioStore:
    return AudioStore(LocalStorage(tmp_path))


def _make_pairs(
    audio_store: AudioStore, count: int,
) -> list[tuple[Beat, TTSBeatRef]]:
    pairs: list[tuple[Beat, TTSBeatRef]] = []
    for i in range(1, count + 1):
        audio_store.save_tts_beat(
            TTSBeat(book_id="alice", provider="elevenlabs_v2", index=i, audio=b"\xff" * 8),
        )
        pairs.append((
            Beat(text=f"b{i}", beat_type=BeatType.NARRATION, character_id=1),
            TTSBeatRef("alice", "elevenlabs_v2", i),
        ))
    return pairs


def test_empty_pipeline_returns_originals(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 2)
    pipeline = AudioTrimmerPipeline()

    # Act
    result = pipeline.apply(pairs, store)

    # Assert
    assert result is pairs


def test_apply_writes_trimmed_sibling_with_single_trimmer(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 3)
    trimmer = _RecordingTrimmer()
    pipeline = AudioTrimmerPipeline([trimmer])

    # Act
    pipeline.apply(pairs, store)

    # Assert
    beat_dir = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_v2"
    final_siblings = sorted(p.name for p in beat_dir.glob("*.trimmed.mp3"))
    assert final_siblings == [
        "beat_0001.trimmed.mp3",
        "beat_0002.trimmed.mp3",
        "beat_0003.trimmed.mp3",
    ]
    assert len(trimmer.calls) == 3


def test_apply_chains_multiple_trimmers_through_step_files(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 1)
    first = _RecordingTrimmer()
    second = _RecordingTrimmer()
    pipeline = AudioTrimmerPipeline([first, second])
    beat_dir = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_v2"

    # Act
    pipeline.apply(pairs, store)

    # Assert
    assert first.calls == [
        (beat_dir / "beat_0001.mp3", beat_dir / "beat_0001.trim_step_0.mp3"),
    ]
    assert second.calls == [
        (
            beat_dir / "beat_0001.trim_step_0.mp3",
            beat_dir / "beat_0001.trimmed.mp3",
        ),
    ]


def test_cleanup_removes_final_siblings_and_intermediates(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 2)
    pipeline = AudioTrimmerPipeline([_RecordingTrimmer(), _RecordingTrimmer()])
    applied = pipeline.apply(pairs, store)

    beat_dir = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_v2"
    surviving_before = sorted(p.name for p in beat_dir.glob("beat_*.mp3"))
    assert any(n.endswith(".trim_step_0.mp3") for n in surviving_before)
    assert any(n.endswith(".trimmed.mp3") for n in surviving_before)

    # Act
    pipeline.cleanup(applied, pairs, store)

    # Assert
    surviving_after = sorted(p.name for p in beat_dir.glob("beat_*.mp3"))
    assert surviving_after == ["beat_0001.mp3", "beat_0002.mp3"]


def test_cleanup_does_not_touch_originals_when_pipeline_empty(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 2)
    pipeline = AudioTrimmerPipeline()
    applied = pipeline.apply(pairs, store)

    # Act
    pipeline.cleanup(applied, pairs, store)

    # Assert
    beat_dir = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_v2"
    surviving = sorted(p.name for p in beat_dir.glob("beat_*.mp3"))
    assert surviving == ["beat_0001.mp3", "beat_0002.mp3"]
