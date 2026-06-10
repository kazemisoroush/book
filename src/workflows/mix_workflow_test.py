"""Tests for MixWorkflow."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_ID, Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, BookContent, BookMetadata, Chapter
from src.repository.book_repository import BookRepository
from src.workflows.mix_workflow import (
    _DEFAULT_GAP_SECONDS,
    MixWorkflow,
)
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"
_BOOK_ID = "test_book"
_ALICE_ID = 2


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str = _BOOK_ID) -> None:
    monkeypatch.setattr(
        "src.workflows.mix_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _make_book(*chapters: Chapter, voices: dict[int, str] | None = None) -> Book:
    registry = CharacterRegistry(characters=[make_default_narrator()])
    registry.add(Character(
        id=_ALICE_ID, name="Alice", description="A young girl",
        sex="female", age="young",
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


def _narratable_chapter(number: int, beat_count: int) -> Chapter:
    beats = []
    for i in range(beat_count):
        char_id = NARRATOR_ID if i % 2 == 0 else _ALICE_ID
        beat_type = BeatType.NARRATION if i % 2 == 0 else BeatType.DIALOGUE
        beats.append(Beat(
            text=f"beat {i}", beat_type=beat_type, character_id=char_id,
        ))
    return Chapter(number=number, title=f"Chapter {number}", beats=beats)


def _make_beat_files(provider_dir: Path, count: int, *, start: int = 1) -> None:
    provider_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(start, start + count):
        (provider_dir / f"beat_{idx:04d}.mp3").write_bytes(b"\x00\x00\x00")


def _fake_repo(book: Book | None) -> MagicMock:
    repo = MagicMock(spec=BookRepository)
    repo.load.return_value = book
    return repo


def test_run_stitches_chapter_into_chapter_01_mp3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narratable_chapter(1, beat_count=3))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs"
    _make_beat_files(provider_dir, count=3)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    expected_output = tmp_path / _BOOK_ID / "audio" / "mix" / "chapter_01.mp3"
    ffmpeg_calls = [c.args[0] for c in run.call_args_list]
    concat_calls = [cmd for cmd in ffmpeg_calls if "-f" in cmd and "concat" in cmd]
    assert any(str(expected_output) in cmd for cmd in concat_calls)


def test_default_gap_produces_400_ms_silence_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narratable_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs"
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    silence_cmds = [
        c.args[0] for c in run.call_args_list
        if "lavfi" in c.args[0]
    ]
    assert len(silence_cmds) == 1
    cmd = silence_cmds[0]
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == str(_DEFAULT_GAP_SECONDS)
    assert _DEFAULT_GAP_SECONDS == 0.4


def test_custom_gap_overrides_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narratable_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs"
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path, gap_seconds=0.75,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    silence_cmds = [
        c.args[0] for c in run.call_args_list if "lavfi" in c.args[0]
    ]
    assert len(silence_cmds) == 1
    cmd = silence_cmds[0]
    assert cmd[cmd.index("-t") + 1] == "0.75"


def test_multi_chapter_assigns_files_with_cumulative_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(
        _narratable_chapter(1, beat_count=2),
        _narratable_chapter(2, beat_count=3),
    )
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs"
    _make_beat_files(provider_dir, count=5)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
    )
    captured: dict[str, list[str]] = {}

    def capture(cmd: list[str], **_kwargs: object) -> MagicMock:
        if "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat":
            list_path = Path(cmd[cmd.index("-i") + 1])
            output_path = cmd[-1]
            captured[output_path] = _beat_filenames(list_path)
        return MagicMock(returncode=0, stdout="", stderr="")

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run", side_effect=capture):
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    mix_dir = tmp_path / _BOOK_ID / "audio" / "mix"
    assert captured[str(mix_dir / "chapter_01.mp3")] == [
        "beat_0001.mp3", "beat_0002.mp3",
    ]
    assert captured[str(mix_dir / "chapter_02.mp3")] == [
        "beat_0003.mp3", "beat_0004.mp3", "beat_0005.mp3",
    ]


def test_chapter_with_no_narratable_beats_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    empty_chapter = Chapter(number=2, title="Empty", beats=[])
    book = _make_book(
        _narratable_chapter(1, beat_count=2),
        empty_chapter,
    )
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs"
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert: only chapter_01.mp3 produced.
    concat_outputs = _concat_output_paths(run)
    assert any("chapter_01.mp3" in p for p in concat_outputs)
    assert not any("chapter_02.mp3" in p for p in concat_outputs)


def test_chapter_with_missing_files_on_disk_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: book says 3 beats but only 2 mp3s exist.
    _patch_resolver(monkeypatch)
    book = _make_book(_narratable_chapter(1, beat_count=3))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / "elevenlabs"
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert: no concat call for chapter 1.
    assert not any("chapter_01.mp3" in p for p in _concat_output_paths(run))


def test_raises_when_book_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    workflow = MixWorkflow(
        repository=_fake_repo(None), books_dir=Path("/tmp/unused"),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))


def test_raises_when_multiple_provider_dirs_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narratable_chapter(1, beat_count=1))
    tts_root = tmp_path / _BOOK_ID / "audio" / "tts"
    _make_beat_files(tts_root / "elevenlabs", count=1)
    _make_beat_files(tts_root / "fish", count=1)

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="Multiple TTS provider"):
        workflow.run(WorkflowRequest(url=_URL))


def test_no_tts_directory_logs_and_returns_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: no TTS output ever produced.
    _patch_resolver(monkeypatch)
    book = _make_book(_narratable_chapter(1, beat_count=1))

    workflow = MixWorkflow(
        repository=_fake_repo(book), books_dir=tmp_path,
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


def _files_in_concat_for(
    run_mock: MagicMock, tmp_path: Path, output_path: Path,
) -> list[str]:
    """Find the concat-list path used to produce `output_path` and read its entries."""
    for call in run_mock.call_args_list:
        cmd = call.args[0]
        if "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat" and cmd[-1] == str(output_path):
            list_path = Path(cmd[cmd.index("-i") + 1])
            return _beat_filenames(list_path)
    return []


def _beat_filenames(concat_list_path: Path) -> list[str]:
    """Return only beat_*.mp3 filenames from a concat list (silence interleavers skipped)."""
    if not concat_list_path.exists():
        return []
    lines = concat_list_path.read_text().splitlines()
    files = [line[len("file '"):-1] for line in lines if line.startswith("file '")]
    return [Path(p).name for p in files if Path(p).name.startswith("beat_")]
