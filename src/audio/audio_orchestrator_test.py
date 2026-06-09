"""Tests for AudioOrchestrator: silence insertion, folder layout, beat synthesis."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audio.audio_orchestrator import AudioOrchestrator, _sanitize_dirname
from src.domain.beat import Beat, BeatType
from src.domain.character import make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)


def _make_beat(character_id: str, beat_type: BeatType = BeatType.NARRATION) -> Beat:
    return Beat(text="Some text.", beat_type=beat_type, character_id=character_id)


def _make_book(chapter_title: str = "Chapter 1") -> Book:
    return Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", releaseDate=None,
            language="en", originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(
                number=1, title=chapter_title,
                sections=[Section(
                    text="Hello world. Goodbye world.",
                    beats=[
                        Beat(text="Hello world.", beat_type=BeatType.NARRATION, character_id="narrator"),
                        Beat(text="Goodbye world.", beat_type=BeatType.NARRATION, character_id="narrator"),
                    ],
                )],
            ),
        ]),
        character_registry=CharacterRegistry(
            characters=[make_default_narrator("book")],
        ),
    )


def _fake_synthesize(text: str, voice_id: str, path: Path, **kwargs: object) -> None:
    path.write_bytes(b"\x00" * 64)


def _fake_ffmpeg_stitch(
    self: AudioOrchestrator,
    beat_paths: list[Path],
    output_path: Path,
    beats: list[Beat] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x00" * 128)
    concat_dir = beat_paths[0].parent if beat_paths else output_path.parent
    (concat_dir / "concat_list.txt").write_text("fake")
    (concat_dir / "silence_150ms.mp3").write_bytes(b"\x00" * 32)


class TestBuildConcatEntries:
    """Silence durations vary by speaker boundary type."""

    def test_same_speaker_boundary_uses_short_silence(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator"), _make_beat("narrator")]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert len(entries) == 3
        assert "silence_150ms" in entries[1].name

    def test_speaker_change_boundary_uses_long_silence(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator"), _make_beat("alice")]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert len(entries) == 3
        assert "silence_400ms" in entries[1].name

    def test_three_beats_produce_two_gaps(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator"), _make_beat("narrator"), _make_beat("alice")]
        beat_paths = [tmp_path / f"beat_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert len(entries) == 5

    def test_single_beat_has_no_silence(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator")]
        beat_paths = [tmp_path / "beat_0.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert entries == beat_paths

    def test_book_title_followed_by_long_silence(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            _make_beat("narrator", beat_type=BeatType.BOOK_TITLE),
            _make_beat("narrator"),
        ]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert "silence_1500ms" in entries[1].name

    def test_chapter_announcement_followed_by_medium_silence(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            _make_beat("narrator", beat_type=BeatType.CHAPTER_ANNOUNCEMENT),
            _make_beat("narrator"),
        ]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert "silence_500ms" in entries[1].name


class TestSanitizeDirname:
    """Replace filesystem-unsafe characters with -."""

    def test_safe_name_unchanged(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("Chapter 1") == "Chapter 1"

    def test_colons_and_slashes_replaced(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("Chapter 1: The/Beginning") == "Chapter 1- The-Beginning"


class TestSynthesizeChapter:
    """Chapter synthesis writes to the correct folder structure."""

    def test_creates_named_subfolder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        provider = MagicMock()
        provider.name = "mock_tts"
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        book = _make_book("Chapter 1")

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert
        assert result == tmp_path / "Chapter 1" / "chapter.mp3"
        assert result.exists()

    def test_debug_keeps_beats_alongside_chapter_mp3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        provider = MagicMock()
        provider.name = "mock_tts"
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, debug=True)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert
        chapter_dir = tmp_path / "Chapter 1"
        beat_files = sorted(chapter_dir.glob("beat_*.mp3"))
        assert len(beat_files) == 2

    def test_normal_mode_preserves_beats_in_provider_subdir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        provider = MagicMock()
        provider.name = "mock_tts"
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, debug=False)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert
        beats_dir = tmp_path / "Chapter 1" / "beats" / "mock_tts"
        beat_files = sorted(beats_dir.glob("beat_*.mp3"))
        assert len(beat_files) == 2

    def test_cached_beat_skips_synthesis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        provider = MagicMock()
        provider.name = "mock_tts"
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, debug=False)
        book = _make_book("Chapter 1")
        beats_dir = tmp_path / "Chapter 1" / "beats" / "mock_tts"
        beats_dir.mkdir(parents=True)
        (beats_dir / "beat_0000.mp3").write_bytes(b"\xff" * 64)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert
        assert provider.synthesize.call_count == 1

    def test_missing_chapter_raises(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        book = _make_book()

        # Act / Assert
        with pytest.raises(ValueError, match="Chapter 99 not found"):
            orch.synthesize_chapter(
                book, chapter_number=99, voice_assignment={"narrator": "v1"},
            )
