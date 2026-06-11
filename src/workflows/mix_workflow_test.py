"""Tests for MixWorkflow."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.silence_trimmer import SilenceTrimmer
from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_ID, Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, BookContent, BookMetadata, Chapter
from src.repository.book_repository import BookRepository
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
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    expected_output = tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_01.mp3"
    ffmpeg_calls = [c.args[0] for c in run.call_args_list]
    concat_calls = [cmd for cmd in ffmpeg_calls if "-f" in cmd and "concat" in cmd]
    assert any(str(expected_output) in cmd for cmd in concat_calls)


def test_concat_list_interleaves_silence_keyed_by_preceding_beat_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: a chapter that exercises every gap-bearing beat type.
    _patch_resolver(monkeypatch)
    book = _make_book(_mixed_intro_chapter(1))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=4)
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert: between every adjacent beat pair the inserted silence matches the
    # gap registered for the *preceding* beat type. Numeric values themselves are
    # subjective tuning knobs and intentionally not pinned here.
    output_path = str(tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_01.mp3")
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
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
        gap_seconds_by_beat_type={BeatType.NARRATION: 0.9},
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    output_path = str(tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_01.mp3")
    files_in_order = [
        Path(line[len("file '"):-1]).name
        for line in captured[output_path]
        if line.startswith("file '")
    ]
    assert "silence_900ms.mp3" in files_in_order  # narration override
    assert "silence_2000ms.mp3" in files_in_order  # chapter announcement default


def test_unique_silence_clips_are_generated_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: 10 narration beats, all same gap → one silence clip, not ten.
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=10))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=10)

    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert: silence clips dedupe by duration — at most one per distinct gap value.
    silence_cmds = [c.args[0] for c in run.call_args_list if "lavfi" in c.args[0]]
    unique_default_gaps = set(_DEFAULT_GAP_SECONDS_BY_BEAT_TYPE.values())
    assert len(silence_cmds) <= len(unique_default_gaps) + 1  # +1 for fallback


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
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
    )

    # Act: ask for chapter 2 only.
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL, start_chapter=2, end_chapter=2))

    # Assert: only chapter_02 was stitched.
    concat_outputs = _concat_output_paths(run)
    assert not any("chapter_01.mp3" in p for p in concat_outputs)
    assert any("chapter_02.mp3" in p for p in concat_outputs)


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
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    mix_dir = tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER
    chapter_1_beats = _beat_filenames(captured[str(mix_dir / "chapter_01.mp3")])
    chapter_2_beats = _beat_filenames(captured[str(mix_dir / "chapter_02.mp3")])
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
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
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
    book = _make_book(_narration_chapter(1, beat_count=3))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)

    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
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
        repository=_fake_repo(None), provider_name=_PROVIDER,
        books_dir=Path("/tmp/unused"),
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
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
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


class _FakeTrimmer(SilenceTrimmer):
    """Records trim() calls and creates a non-empty output file to mimic the real trimmer."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[Path, Path]] = []

    def trim(self, input_path: Path, output_path: Path) -> Path:
        self.calls.append((input_path, output_path))
        output_path.write_bytes(b"\x00" * 8)
        return output_path


def test_trim_invoked_per_beat_when_trimmer_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=3))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=3)
    trimmer = _FakeTrimmer()
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
        silence_trimmer=trimmer,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert len(trimmer.calls) == 3
    for raw, trimmed in trimmer.calls:
        assert raw.name.endswith(".mp3") and not raw.name.endswith(".trimmed.mp3")
        assert trimmed.name.endswith(".trimmed.mp3")
        assert trimmed.parent == raw.parent


def test_concat_uses_trimmed_paths_when_trimming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    trimmer = _FakeTrimmer()
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
        silence_trimmer=trimmer,
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    output_path = str(tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_01.mp3")
    assert _beat_filenames(captured[output_path]) == [
        "beat_0001.trimmed.mp3", "beat_0002.trimmed.mp3",
    ]


def test_no_trimmer_keeps_raw_beats_in_concat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
    )
    captured: dict[str, list[str]] = {}

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        _capture_concat_lists(run, captured)
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    output_path = str(tmp_path / _BOOK_ID / "audio" / "mix" / _PROVIDER / "chapter_01.mp3")
    assert _beat_filenames(captured[output_path]) == ["beat_0001.mp3", "beat_0002.mp3"]


def test_trimmed_siblings_deleted_after_successful_stitch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
        silence_trimmer=_FakeTrimmer(),
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert: trimmed siblings gone, raw beats preserved
    assert sorted(p.name for p in provider_dir.glob("*.trimmed.mp3")) == []
    raw = sorted(
        p.name for p in provider_dir.glob("beat_*.mp3")
        if not p.name.endswith(".trimmed.mp3")
    )
    assert raw == ["beat_0001.mp3", "beat_0002.mp3"]


def test_existing_trimmed_sibling_is_not_retrimmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: a previous run already produced trimmed siblings.
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    (provider_dir / "beat_0001.trimmed.mp3").write_bytes(b"\xaa" * 8)
    (provider_dir / "beat_0002.trimmed.mp3").write_bytes(b"\xaa" * 8)
    trimmer = _FakeTrimmer()
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
        silence_trimmer=trimmer,
    )

    # Act
    with patch("src.workflows.mix_workflow.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert trimmer.calls == []


def test_trimmed_siblings_preserved_on_stitch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: stitch fails so debugging the trimmed inputs is useful.
    _patch_resolver(monkeypatch)
    book = _make_book(_narration_chapter(1, beat_count=2))
    provider_dir = tmp_path / _BOOK_ID / "audio" / "tts" / _PROVIDER
    _make_beat_files(provider_dir, count=2)
    workflow = MixWorkflow(
        repository=_fake_repo(book), provider_name=_PROVIDER, books_dir=tmp_path,
        silence_trimmer=_FakeTrimmer(),
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

    # Assert: trimmed siblings survive for inspection
    surviving = sorted(p.name for p in provider_dir.glob("*.trimmed.mp3"))
    assert surviving == ["beat_0001.trimmed.mp3", "beat_0002.trimmed.mp3"]
