"""Tests for AudioTrimmerPipeline."""
from pathlib import Path

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer
from src.audio.tts.audio_trimmer.audio_trimmer_pipeline import AudioTrimmerPipeline
from src.domain.beat import Beat, BeatType
from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage


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
) -> list[tuple[Beat, str]]:
    pairs: list[tuple[Beat, str]] = []
    for i in range(1, count + 1):
        key = f"raw/beat_{i:04d}.mp3"
        audio_store.write_bytes(key, b"\xff" * 8)
        pairs.append((
            Beat(text=f"b{i}", beat_type=BeatType.NARRATION, character_id=1),
            key,
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
    result = pipeline.apply(pairs, store)

    # Assert
    assert [key for _, key in result] == [
        "raw/beat_0001.trimmed.mp3",
        "raw/beat_0002.trimmed.mp3",
        "raw/beat_0003.trimmed.mp3",
    ]
    assert len(trimmer.calls) == 3


def test_apply_chains_multiple_trimmers_through_step_files(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 1)
    first = _RecordingTrimmer()
    second = _RecordingTrimmer()
    pipeline = AudioTrimmerPipeline([first, second])

    # Act
    result = pipeline.apply(pairs, store)

    # Assert
    assert result[0][1] == "raw/beat_0001.trimmed.mp3"
    assert first.calls == [
        (tmp_path / "raw" / "beat_0001.mp3", tmp_path / "raw" / "beat_0001.trim_step_0.mp3"),
    ]
    assert second.calls == [
        (
            tmp_path / "raw" / "beat_0001.trim_step_0.mp3",
            tmp_path / "raw" / "beat_0001.trimmed.mp3",
        ),
    ]


def test_cleanup_removes_final_siblings_and_intermediates(tmp_path: Path) -> None:
    # Arrange
    store = _audio_store(tmp_path)
    pairs = _make_pairs(store, 2)
    pipeline = AudioTrimmerPipeline([_RecordingTrimmer(), _RecordingTrimmer()])
    applied = pipeline.apply(pairs, store)

    raw_dir = tmp_path / "raw"
    surviving_before = sorted(p.name for p in raw_dir.glob("beat_*.mp3"))
    assert any(n.endswith(".trim_step_0.mp3") for n in surviving_before)
    assert any(n.endswith(".trimmed.mp3") for n in surviving_before)

    # Act
    pipeline.cleanup(applied, pairs, store)

    # Assert
    surviving_after = sorted(p.name for p in raw_dir.glob("beat_*.mp3"))
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
    raw_dir = tmp_path / "raw"
    surviving = sorted(p.name for p in raw_dir.glob("beat_*.mp3"))
    assert surviving == ["beat_0001.mp3", "beat_0002.mp3"]
