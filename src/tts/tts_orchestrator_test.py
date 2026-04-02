"""Tests for TTSOrchestrator — silence insertion and chapter folder output.

These tests verify:
  - Silence clips are inserted between consecutive TTS segments at stitch time,
    with duration varying by boundary type (same speaker vs. speaker change).
  - Output goes to named per-chapter subfolders: ``audio/{chapter_title}/chapter.mp3``.
  - ``debug=True`` retains individual ``seg_NNNN.mp3`` files alongside ``chapter.mp3``.
  - ``debug=False`` (default) cleans up segment files after stitching.
  - ``_sanitize_dirname`` replaces filesystem-unsafe characters.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.domain.models import (
    Book, BookContent, BookMetadata, Chapter, CharacterRegistry,
    Section, Segment, SegmentType,
)
from src.tts.tts_orchestrator import TTSOrchestrator, _sanitize_dirname


def _make_segment(character_id: str) -> Segment:
    """Create a minimal speakable segment with the given character_id."""
    return Segment(
        text="Some text.",
        segment_type=SegmentType.NARRATION,
        character_id=character_id,
    )


class TestBuildConcatEntriesSameSpeaker:
    """Same-speaker boundaries use the short silence duration."""

    def test_same_speaker_boundary_uses_short_silence(self, tmp_path: Path) -> None:
        """Two segments with the same character_id produce a silence gap
        of silence_same_speaker_ms duration."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [_make_segment("narrator"), _make_segment("narrator")]
        seg_paths = [tmp_path / "seg_0.mp3", tmp_path / "seg_1.mp3"]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — 2 segment entries + 1 silence entry = 3 total
        assert len(entries) == 3
        # The middle entry should be a silence file path containing '150'
        silence_entry = entries[1]
        assert "silence_150ms" in silence_entry.name


class TestBuildConcatEntriesSpeakerChange:
    """Speaker-change boundaries use the long silence duration."""

    def test_speaker_change_boundary_uses_long_silence(self, tmp_path: Path) -> None:
        """Two segments with different character_id produce a silence gap
        of silence_speaker_change_ms duration."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [_make_segment("narrator"), _make_segment("alice")]
        seg_paths = [tmp_path / "seg_0.mp3", tmp_path / "seg_1.mp3"]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — 2 segment entries + 1 silence entry = 3 total
        assert len(entries) == 3
        silence_entry = entries[1]
        assert "silence_400ms" in silence_entry.name


class TestBuildConcatEntriesGapCount:
    """N segments produce exactly N-1 silence gaps."""

    def test_three_segments_produce_two_gaps(self, tmp_path: Path) -> None:
        """Three segments must yield 3 segment entries + 2 silence entries = 5."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [
            _make_segment("narrator"),
            _make_segment("alice"),
            _make_segment("narrator"),
        ]
        seg_paths = [tmp_path / f"seg_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — 3 segments + 2 gaps = 5
        assert len(entries) == 5
        # Positions 1 and 3 are silence entries
        assert "silence_" in entries[1].name
        assert "silence_" in entries[3].name


class TestBuildConcatEntriesSingleSegment:
    """A single segment produces no silence clips."""

    def test_single_segment_has_no_silence(self, tmp_path: Path) -> None:
        """One segment must yield exactly 1 entry with no silence."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [_make_segment("narrator")]
        seg_paths = [tmp_path / "seg_0.mp3"]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert
        assert len(entries) == 1
        assert entries[0] == seg_paths[0]


class TestBuildConcatEntriesCustomDurations:
    """Custom silence durations are respected."""

    def test_custom_silence_durations(self, tmp_path: Path) -> None:
        """Non-default silence durations are reflected in silence file names."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            silence_same_speaker_ms=200,
            silence_speaker_change_ms=500,
        )
        segments = [
            _make_segment("narrator"),
            _make_segment("narrator"),
            _make_segment("alice"),
        ]
        seg_paths = [tmp_path / f"seg_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — first gap is same-speaker (200ms), second is change (500ms)
        assert "silence_200ms" in entries[1].name
        assert "silence_500ms" in entries[3].name


class TestSilenceClipReuse:
    """Silence clips of the same duration are generated once and reused."""

    def test_same_duration_silence_paths_are_identical(self, tmp_path: Path) -> None:
        """Multiple same-speaker gaps should reference the same silence file path."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [
            _make_segment("narrator"),
            _make_segment("narrator"),
            _make_segment("narrator"),
        ]
        seg_paths = [tmp_path / f"seg_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — both silence entries reference the exact same path
        assert entries[1] == entries[3]


# ------------------------------------------------------------------
# Helpers for synthesize_chapter tests
# ------------------------------------------------------------------

def _make_book(chapter_title: str = "Chapter 1") -> Book:
    """Create a minimal Book with one chapter containing two narration segments."""
    return Book(
        metadata=BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language="en",
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title=chapter_title,
                    sections=[
                        Section(
                            text="Hello world. Goodbye world.",
                            segments=[
                                Segment(
                                    text="Hello world.",
                                    segment_type=SegmentType.NARRATION,
                                    character_id="narrator",
                                ),
                                Segment(
                                    text="Goodbye world.",
                                    segment_type=SegmentType.NARRATION,
                                    character_id="narrator",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        character_registry=CharacterRegistry.with_default_narrator(),
    )


def _fake_synthesize(text: str, voice_id: str, path: Path, **kwargs: object) -> None:
    """Stub TTS provider that writes a tiny file instead of calling an API."""
    path.write_bytes(b"\x00" * 64)


def _fake_ffmpeg_stitch(
    self: TTSOrchestrator,
    segment_paths: list[Path],
    output_path: Path,
    segments: list[Segment] | None = None,
) -> None:
    """Replace _stitch_with_ffmpeg to avoid a real ffmpeg dependency in tests."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x00" * 128)
    # Simulate concat_list.txt and silence files that ffmpeg would leave behind
    concat_dir = segment_paths[0].parent if segment_paths else output_path.parent
    (concat_dir / "concat_list.txt").write_text("fake")
    (concat_dir / "silence_150ms.mp3").write_bytes(b"\x00" * 32)


# ------------------------------------------------------------------
# _sanitize_dirname tests
# ------------------------------------------------------------------


class TestSanitizeDirname:
    """_sanitize_dirname replaces filesystem-unsafe characters."""

    def test_safe_name_unchanged(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("Chapter 1") == "Chapter 1"

    def test_colons_replaced(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("Chapter 1: The Beginning") == "Chapter 1- The Beginning"

    def test_slashes_replaced(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("A/B\\C") == "A-B-C"

    def test_multiple_unsafe_chars(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname('He said "Hello?" <yes>') == 'He said -Hello-- -yes-'


# ------------------------------------------------------------------
# synthesize_chapter — named subfolder output
# ------------------------------------------------------------------


class TestSynthesizeChapterNamedSubfolder:
    """synthesize_chapter writes to output_dir/{chapter_title}/chapter.mp3."""

    def test_synthesize_chapter_creates_named_subfolder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output path should be output_dir/{chapter_title}/chapter.mp3."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        book = _make_book("Chapter 1")

        # Act
        result = orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        assert result == tmp_path / "Chapter 1" / "chapter.mp3"
        assert result.exists()


# ------------------------------------------------------------------
# synthesize_chapter — debug mode keeps segments
# ------------------------------------------------------------------


class TestSynthesizeChapterDebugKeepsSegments:
    """debug=True retains seg_NNNN.mp3 files alongside chapter.mp3."""

    def test_synthesize_chapter_debug_keeps_segments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In debug mode, segment files remain in the chapter folder."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path, debug=True)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — segment files persist
        chapter_dir = tmp_path / "Chapter 1"
        seg_files = sorted(chapter_dir.glob("seg_*.mp3"))
        assert len(seg_files) == 2
        assert seg_files[0].name == "seg_0000.mp3"
        assert seg_files[1].name == "seg_0001.mp3"


# ------------------------------------------------------------------
# synthesize_chapter — normal mode cleans segments
# ------------------------------------------------------------------


class TestSynthesizeChapterNormalCleansSegments:
    """debug=False (default) removes seg_NNNN.mp3 after stitching."""

    def test_synthesize_chapter_normal_cleans_segments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In normal mode, no seg_*.mp3 files remain in the chapter folder."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path, debug=False)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — no segment files in the chapter folder
        chapter_dir = tmp_path / "Chapter 1"
        seg_files = list(chapter_dir.glob("seg_*.mp3"))
        assert seg_files == []
        # But chapter.mp3 still exists
        assert (chapter_dir / "chapter.mp3").exists()
