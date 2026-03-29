"""Tests for TTSOrchestrator.

AC4: NARRATION and DIALOGUE segments are synthesised.
     ILLUSTRATION, COPYRIGHT, and OTHER segments are skipped.
AC5: Per-segment MP3s are stitched into output/chapter_01.mp3 using ffmpeg.
AC6: Book struct is saved to output/book.json as a byproduct.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.tts.tts_orchestrator import TTSOrchestrator
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Character,
    CharacterRegistry,
    Section,
    Segment,
    SegmentType,
)


def _make_book(sections: list[Section] | None = None) -> Book:
    """Build a minimal Book with Chapter 1."""
    if sections is None:
        sections = [
            Section(
                text="Hello world",
                segments=[
                    Segment(text="Hello", segment_type=SegmentType.NARRATION, character_id="narrator"),
                ],
            )
        ]
    metadata = BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language="en",
        originalPublication=None,
        credits=None,
    )
    content = BookContent(
        chapters=[
            Chapter(number=1, title="Chapter 1", sections=sections)
        ]
    )
    registry = CharacterRegistry.with_default_narrator()
    return Book(metadata=metadata, content=content, character_registry=registry)


def _make_voice_assignment() -> dict[str, str]:
    return {"narrator": "narrator_voice_id"}


class TestTTSOrchestratorSynthesisFilter:
    """AC4: NARRATION and DIALOGUE synthesised; others skipped."""

    def test_narration_segment_is_synthesised(self, tmp_path: Path) -> None:
        """NARRATION segments must trigger a synthesize() call."""
        sections = [
            Section(
                text="Some narration.",
                segments=[
                    Segment(
                        text="Some narration.",
                        segment_type=SegmentType.NARRATION,
                        character_id="narrator",
                    )
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        mock_provider.synthesize.return_value = None

        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        assert mock_provider.synthesize.call_count == 1

    def test_dialogue_segment_is_synthesised(self, tmp_path: Path) -> None:
        """DIALOGUE segments must trigger a synthesize() call."""
        sections = [
            Section(
                text='"Hello," said Alice.',
                segments=[
                    Segment(
                        text="Hello",
                        segment_type=SegmentType.DIALOGUE,
                        character_id="alice",
                    )
                ],
            )
        ]
        book = _make_book(sections)
        book.character_registry.add(
            Character(character_id="alice", name="Alice", sex="female", age="young")
        )
        voice_assignment = {"narrator": "nv", "alice": "av"}

        mock_provider = Mock()
        mock_provider.synthesize.return_value = None

        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, voice_assignment)

        assert mock_provider.synthesize.call_count == 1

    def test_illustration_segment_is_skipped(self, tmp_path: Path) -> None:
        """ILLUSTRATION segments must NOT trigger a synthesize() call."""
        sections = [
            Section(
                text="[Illustration: A figure]",
                segments=[
                    Segment(
                        text="[Illustration: A figure]",
                        segment_type=SegmentType.ILLUSTRATION,
                        character_id=None,
                    )
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        mock_provider.synthesize.assert_not_called()

    def test_copyright_segment_is_skipped(self, tmp_path: Path) -> None:
        """COPYRIGHT segments must NOT trigger a synthesize() call."""
        sections = [
            Section(
                text="Copyright 2020",
                segments=[
                    Segment(
                        text="Copyright 2020",
                        segment_type=SegmentType.COPYRIGHT,
                        character_id=None,
                    )
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        mock_provider.synthesize.assert_not_called()

    def test_other_segment_is_skipped(self, tmp_path: Path) -> None:
        """OTHER segments must NOT trigger a synthesize() call."""
        sections = [
            Section(
                text="Page 42",
                segments=[
                    Segment(
                        text="Page 42",
                        segment_type=SegmentType.OTHER,
                        character_id=None,
                    )
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        mock_provider.synthesize.assert_not_called()

    def test_mixed_segments_only_synthesise_narration_and_dialogue(self, tmp_path: Path) -> None:
        """In a section with mixed types, only NARRATION/DIALOGUE are synthesised."""
        sections = [
            Section(
                text="Full section",
                segments=[
                    Segment(text="Narration part.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                    Segment(text="[Illustration]", segment_type=SegmentType.ILLUSTRATION, character_id=None),
                    Segment(text="Dialogue part.", segment_type=SegmentType.DIALOGUE, character_id="narrator"),
                    Segment(text="Page 1", segment_type=SegmentType.OTHER, character_id=None),
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        # Only NARRATION + DIALOGUE = 2 calls
        assert mock_provider.synthesize.call_count == 2


class TestTTSOrchestratorVoiceId:
    """The correct voice_id is passed to synthesize() for each segment."""

    def test_narrator_segment_uses_narrator_voice(self, tmp_path: Path) -> None:
        """synthesize() for a narrator segment must receive the narrator's voice_id."""
        sections = [
            Section(
                text="Narration.",
                segments=[
                    Segment(text="Narration.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, {"narrator": "narrator_vid"})

        call_kwargs = mock_provider.synthesize.call_args
        # Second positional arg is voice_id
        assert call_kwargs.args[1] == "narrator_vid"

    def test_character_segment_uses_character_voice(self, tmp_path: Path) -> None:
        """synthesize() for a character's dialogue uses that character's voice_id."""
        sections = [
            Section(
                text='"Hi," said Bob.',
                segments=[
                    Segment(text="Hi", segment_type=SegmentType.DIALOGUE, character_id="bob"),
                ],
            )
        ]
        book = _make_book(sections)
        book.character_registry.add(Character(character_id="bob", name="Bob"))

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, {"narrator": "nv", "bob": "bob_vid"})

        call_kwargs = mock_provider.synthesize.call_args
        assert call_kwargs.args[1] == "bob_vid"


class TestTTSOrchestratorFfmpegStitch:
    """AC5: Per-segment MP3s are stitched via ffmpeg."""

    def test_ffmpeg_is_called_to_stitch_segments(self, tmp_path: Path) -> None:
        """synthesize_chapter() must call subprocess.run with ffmpeg."""
        sections = [
            Section(
                text="Two segments.",
                segments=[
                    Segment(text="First.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                    Segment(text="Second.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        # ffmpeg must be called
        assert mock_run.called
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "ffmpeg"

    def test_output_path_is_chapter_01_mp3(self, tmp_path: Path) -> None:
        """The stitched output file must be output/chapter_01.mp3."""
        sections = [
            Section(
                text="Segment.",
                segments=[
                    Segment(text="Segment.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        assert result == tmp_path / "chapter_01.mp3"

    def test_ffmpeg_concat_includes_all_synthesised_segments(self, tmp_path: Path) -> None:
        """The ffmpeg concat list must include exactly the synthesised segments."""
        sections = [
            Section(
                text="Narration then dialogue.",
                segments=[
                    Segment(text="Narration.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                    Segment(text="Skip me.", segment_type=SegmentType.ILLUSTRATION, character_id=None),
                    Segment(text="Dialogue.", segment_type=SegmentType.DIALOGUE, character_id="narrator"),
                ],
            )
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        # synthesize called twice (NARRATION + DIALOGUE)
        assert mock_provider.synthesize.call_count == 2


class TestTTSOrchestratorBookJson:
    """AC6: Book struct saved to output/book.json."""

    def test_book_json_is_saved_to_output_dir(self, tmp_path: Path) -> None:
        """synthesize_chapter() must write book.json to the output dir."""
        book = _make_book()

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        book_json_path = tmp_path / "book.json"
        assert book_json_path.exists()

    def test_book_json_is_valid_json(self, tmp_path: Path) -> None:
        """book.json must be parseable JSON."""
        book = _make_book()

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        book_json_path = tmp_path / "book.json"
        data = json.loads(book_json_path.read_text())
        assert "metadata" in data
        assert "content" in data
        assert "character_registry" in data

    def test_book_json_contains_correct_title(self, tmp_path: Path) -> None:
        """book.json must contain the book's title."""
        book = _make_book()

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        data = json.loads((tmp_path / "book.json").read_text())
        assert data["metadata"]["title"] == "Test Book"


class TestTTSOrchestratorModule:
    """Module-level sanity checks."""

    def test_module_has_structlog_logger(self) -> None:
        """tts_orchestrator module must have a module-level structlog logger."""
        import src.tts.tts_orchestrator as module
        assert hasattr(module, "logger")
        assert hasattr(module.logger, "info")

    def test_synthesize_chapter_raises_when_chapter_not_found(self, tmp_path: Path) -> None:
        """synthesize_chapter() must raise ValueError when chapter number not in book."""
        book = _make_book()  # only has chapter 1

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with pytest.raises(ValueError, match="Chapter 99 not found"):
            orchestrator.synthesize_chapter(book, 99, _make_voice_assignment())

    def test_synthesize_chapter_skips_sections_without_segments(self, tmp_path: Path) -> None:
        """Sections with segments=None are gracefully skipped."""
        sections = [
            Section(text="No segments here.", segments=None),
            Section(
                text="Has segments.",
                segments=[
                    Segment(text="Has segments.", segment_type=SegmentType.NARRATION, character_id="narrator"),
                ],
            ),
        ]
        book = _make_book(sections)

        mock_provider = Mock()
        orchestrator = TTSOrchestrator(mock_provider, tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            orchestrator.synthesize_chapter(book, 1, _make_voice_assignment())

        # Only the section with segments triggers synthesis
        assert mock_provider.synthesize.call_count == 1
