"""Tests for MixWorkflow."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.tts.audio_trimmer.audio_trimmer_pipeline import AudioTrimmerPipeline
from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_ID, Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, BookContent, BookMetadata, Chapter
from src.repository.book_repository import BookRepository
from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage
from src.workflows.mix_workflow import (
    _DEFAULT_GAP_SECONDS_BY_BEAT_TYPE,
    MixWorkflow,
)
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"
_BOOK_ID = "test_book"
_PROVIDER = "elevenlabs"
_ALICE_ID = 2


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str = _BOOK_ID) -> None:
    monkeypatch.setattr(
        "src.workflows.mix_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _audio_store(tmp_path: Path) -> AudioStore:
    return AudioStore(LocalStorage(tmp_path))


def _make_book(*chapters: Chapter, voices: dict[int, str] | None = None) -> Book:
    registry = CharacterRegistry(characters=[make_default_narrator()])
    registry.add(Character(
        id=_ALICE_ID, name="Alice",
        gender="female", age="young", accent="british",
    ))
    return Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=list(chapters)),
        character_registry=registry,
        voice_assignments=voices if voices is not None
        else {NARRATOR_ID: "v_narrator", _ALICE_ID: "v_alice"},
    )


def _narration_chapter(number: int, beat_count: int) -> Chapter:
    beats = [
        Beat(text=f"beat {i}", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID)
        for i in range(beat_count)
    ]
    return Chapter(number=number, title=f"Chapter {number}", beats=beats)


def _mixed_intro_chapter(number: int) -> Chapter:
    """Chapter that opens with title + announcement + narration + dialogue."""
    return Chapter(
        number=number, title=f"Chapter {number}",
        beats=[
            Beat(text="Title", beat_type=BeatType.BOOK_TITLE, character_id=NARRATOR_ID),
            Beat(text="Ch announce", beat_type=BeatType.CHAPTER_ANNOUNCEMENT,
                 character_id=NARRATOR_ID),
            Beat(text="Once upon...", beat_type=BeatType.NARRATION,
                 character_id=NARRATOR_ID),
            Beat(text="Hello!", beat_type=BeatType.DIALOGUE, character_id=_ALICE_ID),
        ],
    )


def _make_beat_files(provider_dir: Path, count: int, *, start: int = 1) -> None:
    provider_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(start, start + count):
        (provider_dir / f"beat_{idx:04d}.mp3").write_bytes(b"\x00\x00\x00")


def _fake_repo(book: Book | None) -> MagicMock:
    repo = MagicMock(spec=BookRepository)
    repo.load.return_value = book
    return repo


def _capture_concat_lists(
    run_mock: MagicMock,
    captured: dict[str, list[str]],
) -> MagicMock:
    """Make `run_mock.side_effect` capture concat-list filenames before deletion."""
    def side_effect(cmd: list[str], **_kwargs: object) -> MagicMock:
        if "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat":
            list_path = Path(cmd[cmd.index("-i") + 1])
            output_path = cmd[-1]
            captured[output_path] = list_path.read_text().splitlines()
        return MagicMock(returncode=0, stdout="", stderr="")
    run_mock.side_effect = side_effect
    return run_mock


def test_run_stitches_chapter_into_chapter_01_mp3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=3))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=3)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    expected_output = tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_001.mp3"
    ffmpeg_calls = [c.args[0] for c in run.call_args_list]
    concat_calls = [cmd for cmd in ffmpeg_calls if "-f" in cmd and "concat" in cmd]
    assert any(str(expected_output) in cmd for cmd in concat_calls)


def test_concat_list_interleaves_silence_keyed_by_preceding_beat_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_mixed_intro_chapter(1))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=4)
    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    output_path = str(tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_001.mp3")
    files = [
        Path(line[len("file '"):-1]).name
        for line in captured[output_path]
        if line.startswith("file '")
    ]
    preceding_types = [BeatType.BOOK_TITLE, BeatType.CHAPTER_ANNOUNCEMENT, BeatType.NARRATION]
    expected_silences = [
        f"silence_{int(round(_DEFAULT_GAP_SECONDS_BY_BEAT_TYPE[t] * 1000))}ms.mp3"
        for t in preceding_types
    ]
    assert [files[i] for i in (1, 3, 5)] == expected_silences


def test_partial_override_merges_with_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: override only NARRATION; CHAPTER_ANNOUNCEMENT stays at default.
    _patch_resolver(monkeypatch)
    book = _make_book(_mixed_intro_chapter(1))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=4)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
        gap_seconds_by_beat_type={BeatType.NARRATION: 0.9},
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    output_path = str(tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_001.mp3")
    files_in_order = [
        Path(line[len("file '"):-1]).name
        for line in captured[output_path]
        if line.startswith("file '")
    ]
    assert "silence_900ms.mp3" in files_in_order
    assert "silence_2000ms.mp3" in files_in_order


def test_unique_silence_clips_are_generated_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=10))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=10)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    silence_cmds = [c.args[0] for c in run.call_args_list if "lavfi" in c.args[0]]
    unique_default_gaps = set(_DEFAULT_GAP_SECONDS_BY_BEAT_TYPE.values())
    assert len(silence_cmds) <= len(unique_default_gaps) + 1


def test_run_respects_chapter_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(
        _narration_chapter(1, beat_count=2),
        _narration_chapter(2, beat_count=3),
    )
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=5)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL, start_chapter=2, end_chapter=2))

    # Assert
    concat_outputs = _concat_output_paths(run)
    assert not any("chapter_001.mp3" in p for p in concat_outputs)
    assert any("chapter_002.mp3" in p for p in concat_outputs)


def test_multi_chapter_assigns_files_with_cumulative_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(
        _narration_chapter(1, beat_count=2),
        _narration_chapter(2, beat_count=3),
    )
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=5)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    mix_dir = tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER
    chapter_1_beats = _beat_filenames(captured[str(mix_dir / "chapter_001.mp3")])
    chapter_2_beats = _beat_filenames(captured[str(mix_dir / "chapter_002.mp3")])
    assert chapter_1_beats == ["beat_0001.mp3", "beat_0002.mp3"]
    assert chapter_2_beats == [
        "beat_0003.mp3", "beat_0004.mp3", "beat_0005.mp3",
    ]


def test_chapter_with_no_narratable_beats_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    empty_chapter = Chapter(number=2, title="Empty", beats=[])
    book = _make_book(
        _narration_chapter(1, beat_count=2),
        empty_chapter,
    )
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    concat_outputs = _concat_output_paths(run)
    assert any("chapter_001.mp3" in p for p in concat_outputs)
    assert not any("chapter_002.mp3" in p for p in concat_outputs)


def test_chapter_with_missing_files_on_disk_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: book says 3 beats but only 2 mp3s exist.
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=3))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert not any("chapter_001.mp3" in p for p in _concat_output_paths(run))


def test_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    workflow = MixWorkflow(
        repositories=[_fake_repo(None)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))


def test_no_tts_directory_logs_and_returns_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: no TTS output ever produced.
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=1))

    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        result = workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert result is book
    run.assert_not_called()


def _concat_output_paths(run_mock: MagicMock) -> list[str]:
    paths: list[str] = []
    for call in run_mock.call_args_list:
        cmd = call.args[0]
        if "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat":
            paths.append(cmd[-1])
    return paths


def _beat_filenames(concat_lines: list[str]) -> list[str]:
    """Return only beat_*.mp3 filenames from a concat list (silence interleavers skipped)."""
    files = [
        Path(line[len("file '"):-1]).name
        for line in concat_lines if line.startswith("file '")
    ]
    return [f for f in files if f.startswith("beat_")]


def test_trimmer_pipeline_apply_and_cleanup_run_around_stitch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    pipeline = MagicMock(spec=AudioTrimmerPipeline)
    pipeline.apply.side_effect = lambda pairs, _store: pairs
    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
        trimmer_pipeline=pipeline,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    pipeline.apply.assert_called_once()
    pipeline.cleanup.assert_called_once()


def _make_chunk_files(chunk_dir: Path, count: int) -> None:
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(1, count + 1):
        (chunk_dir / f"chunk_{idx:04d}.mp3").write_bytes(b"\x00\x00\x00")


def test_dialogue_provider_concatenates_chunks_per_chapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=3))
    chunk_dir = (
        tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs_dialogue" / "chapter_001"
    )
    _make_chunk_files(chunk_dir, count=3)
    captured: dict[str, list[str]] = {}
    workflow = MixWorkflow(
        repositories=[_fake_repo(book)],
        provider_name="elevenlabs_dialogue",
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    expected_output = str(
        tmp_path / _BOOK_ID / "audio" / "mix" / "elevenlabs_dialogue" / "chapter_001.mp3"
    )
    assert expected_output in captured
    concat_lines = captured[expected_output]
    chunk_lines = [line for line in concat_lines if "chunk_" in line]
    silence_lines = [line for line in concat_lines if "silence_" in line]
    assert len(chunk_lines) == 3
    assert len(silence_lines) == 2
    silence_clip_calls = [
        c.args[0] for c in run.call_args_list
        if "anullsrc" in " ".join(c.args[0])
    ]
    assert len(silence_clip_calls) == 1


def test_dialogue_provider_skips_chapter_with_no_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: the provider prefix has a sibling file so list_prefix is non-empty,
    # but the specific chapter has no chunks.
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    other_chapter_dir = (
        tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs_dialogue" / "chapter_002"
    )
    _make_chunk_files(other_chapter_dir, count=1)
    workflow = MixWorkflow(
        repositories=[_fake_repo(book)],
        provider_name="elevenlabs_dialogue",
        audio_store=_audio_store(tmp_path),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert: no concat call mentions chapter_001.
    concat_outputs = _concat_output_paths(run)
    assert not any("chapter_001.mp3" in p for p in concat_outputs)


def test_trimmer_pipeline_cleanup_skipped_on_stitch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    pipeline = MagicMock(spec=AudioTrimmerPipeline)
    pipeline.apply.side_effect = lambda pairs, _store: pairs
    workflow = MixWorkflow(
        repositories=[_fake_repo(book)], provider_name=_PROVIDER,
        audio_store=_audio_store(tmp_path),
        trimmer_pipeline=pipeline,
    )

    def fail_on_concat(cmd: list[str], **_: object) -> MagicMock:
        if "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat":
            return MagicMock(returncode=1, stdout="", stderr="ffmpeg boom")
        return MagicMock(returncode=0, stdout="", stderr="")

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.side_effect = fail_on_concat
        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            workflow.run(WorkflowRequest(url=_URL))

    # Assert
    pipeline.cleanup.assert_not_called()
