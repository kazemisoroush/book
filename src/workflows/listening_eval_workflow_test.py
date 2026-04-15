"""Tests for ListeningEvalWorkflow — the golden-passage-based eval workflow.

Coverage:
- GoldenE2EPassage stores a Book directly (no flat book_title/author/etc. fields)
- run() uses passage.book directly without mapping
- Synthetic sections (book_title + chapter_announcement) are pre-baked in the Book
- AI segmentation loop skips sections with pre-existing segments
- Voice assigner is called with the final character registry
- AudioOrchestrator synthesizes each chapter
- create() factory wires AWSBedrockProvider as ai_provider
- dracula_arrival constant carries a Book with the expected metadata
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.tts.voice_assigner import VoiceEntry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    CharacterRegistry,
    Section,
    Segment,
    SegmentType,
)
from src.workflows.listening_eval_workflow import (
    ALL_E2E_PASSAGES,
    GoldenE2EPassage,
    ListeningEvalWorkflow,
    dracula_arrival,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(
    title: str = "Test Book",
    author: str = "Test Author",
    chapter_number: int = 3,
    chapter_title: str = "Test Chapter",
    section_texts: list[str] | None = None,
) -> Book:
    """Construct a minimal Book for use in GoldenE2EPassage fixtures.

    Prepends pre-baked book_title and chapter_announcement sections matching
    the production contract (dracula_arrival embeds these at definition time).
    """
    texts = section_texts or ["First paragraph.", "Second paragraph with dialogue."]
    synthetic_sections: list[Section] = [
        Section(
            text=f"{title}, by {author}.",
            section_type="book_title",
            segments=[Segment(
                text=f"{title}, by {author}.",
                segment_type=SegmentType.BOOK_TITLE,
                character_id="narrator",
            )],
        ),
        Section(
            text=f"Chapter {chapter_number}. {chapter_title}.",
            section_type="chapter_announcement",
            segments=[Segment(
                text=f"Chapter {chapter_number}. {chapter_title}.",
                segment_type=SegmentType.CHAPTER_ANNOUNCEMENT,
                character_id="narrator",
            )],
        ),
    ]
    content_sections = [Section(text=t) for t in texts]
    sections = synthetic_sections + content_sections
    chapter = Chapter(number=chapter_number, title=chapter_title, sections=sections)
    metadata = BookMetadata(
        title=title,
        author=author,
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )
    return Book(metadata=metadata, content=BookContent(chapters=[chapter]))


def _minimal_passage() -> GoldenE2EPassage:
    """Return a small passage with a 2-section Book for fast test execution."""
    return GoldenE2EPassage(
        name="test_passage",
        book=_make_book(),
        gutenberg_url="https://example.com",
        expected_features=["narration", "dialogue"],
        notes="Test passage",
    )


def _make_workflow(tmp_path: Path) -> tuple[ListeningEvalWorkflow, MagicMock, MagicMock]:
    """Create a ListeningEvalWorkflow with mock providers.

    Returns:
        (workflow, mock_ai_provider, mock_tts_provider)
    """
    mock_ai_provider = MagicMock()
    mock_tts_provider = MagicMock()
    voice_entries = [
        VoiceEntry(voice_id="v1", name="Narrator", labels={}),
        VoiceEntry(voice_id="v2", name="Character", labels={}),
    ]
    workflow = ListeningEvalWorkflow(
        ai_provider=mock_ai_provider,
        voice_entries=voice_entries,
        tts_provider=mock_tts_provider,
        sound_effect_provider=MagicMock(),
        ambient_provider=MagicMock(),
        books_dir=tmp_path,
    )
    return workflow, mock_ai_provider, mock_tts_provider


# ---------------------------------------------------------------------------
# GoldenE2EPassage shape
# ---------------------------------------------------------------------------


class TestGoldenE2EPassageShape:
    """Verify the new GoldenE2EPassage carries a Book directly."""

    def test_passage_has_book_field(self) -> None:
        # Arrange / Act
        passage = _minimal_passage()

        # Assert
        assert isinstance(passage.book, Book)

    def test_passage_has_no_book_title_field(self) -> None:
        # Arrange / Act
        passage = _minimal_passage()

        # Assert — flat fields from old design must not exist
        assert not hasattr(passage, "book_title")

    def test_passage_has_no_author_field(self) -> None:
        # Arrange / Act
        passage = _minimal_passage()

        # Assert
        assert not hasattr(passage, "author")

    def test_passage_has_no_chapter_number_field(self) -> None:
        # Arrange / Act
        passage = _minimal_passage()

        # Assert
        assert not hasattr(passage, "chapter_number")

    def test_passage_has_no_sections_field(self) -> None:
        # Arrange / Act
        passage = _minimal_passage()

        # Assert
        assert not hasattr(passage, "sections")

    def test_eval_only_fields_present(self) -> None:
        # Arrange / Act
        passage = _minimal_passage()

        # Assert
        assert passage.name == "test_passage"
        assert passage.gutenberg_url == "https://example.com"
        assert passage.expected_features == ["narration", "dialogue"]
        assert passage.notes == "Test passage"


# ---------------------------------------------------------------------------
# dracula_arrival constant
# ---------------------------------------------------------------------------


class TestDraculaArrivalConstant:
    """Verify dracula_arrival is a GoldenE2EPassage with a Book."""

    def test_dracula_arrival_has_book(self) -> None:
        # Assert
        assert isinstance(dracula_arrival.book, Book)

    def test_dracula_arrival_book_title(self) -> None:
        # Assert
        assert dracula_arrival.book.metadata.title == "Dracula"

    def test_dracula_arrival_book_author(self) -> None:
        # Assert
        assert dracula_arrival.book.metadata.author == "Bram Stoker"

    def test_dracula_arrival_book_has_chapters(self) -> None:
        # Assert
        assert len(dracula_arrival.book.content.chapters) >= 1

    def test_dracula_arrival_book_sections_non_empty(self) -> None:
        # Assert
        chapter = dracula_arrival.book.content.chapters[0]
        assert len(chapter.sections) >= 1

    def test_dracula_arrival_in_all_passages(self) -> None:
        # Assert
        assert dracula_arrival in ALL_E2E_PASSAGES

    def test_dracula_arrival_first_section_is_book_title(self) -> None:
        # Arrange
        chapter = dracula_arrival.book.content.chapters[0]

        # Act
        first = chapter.sections[0]

        # Assert
        assert first.section_type == "book_title"

    def test_dracula_arrival_second_section_is_chapter_announcement(self) -> None:
        # Arrange
        chapter = dracula_arrival.book.content.chapters[0]

        # Act
        second = chapter.sections[1]

        # Assert
        assert second.section_type == "chapter_announcement"

    def test_dracula_arrival_book_title_section_has_correct_segments(self) -> None:
        # Arrange
        chapter = dracula_arrival.book.content.chapters[0]

        # Act
        first = chapter.sections[0]

        # Assert
        assert first.segments is not None
        assert first.segments[0].segment_type == SegmentType.BOOK_TITLE
        assert first.segments[0].character_id == "narrator"

    def test_dracula_arrival_chapter_announcement_section_has_correct_segments(self) -> None:
        # Arrange
        chapter = dracula_arrival.book.content.chapters[0]

        # Act
        second = chapter.sections[1]

        # Assert
        assert second.segments is not None
        assert second.segments[0].segment_type == SegmentType.CHAPTER_ANNOUNCEMENT
        assert second.segments[0].character_id == "narrator"


# ---------------------------------------------------------------------------
# Book construction — run() uses passage.book directly
# ---------------------------------------------------------------------------


class TestBookPassthrough:
    """Verify run() uses passage.book without rebuilding it."""

    def test_run_returns_book_with_correct_metadata(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, mock_ai, _ = _make_workflow(tmp_path)
        mock_ai.complete.return_value = '{"segments": [{"text": "First paragraph.", "type": "narration", "character_id": "narrator"}]}'

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            mock_parser_instance = MagicMock()
            narrator_registry = CharacterRegistry.with_default_narrator()
            mock_parser_instance.parse.return_value = (
                [Segment(text="First paragraph.", segment_type=SegmentType.NARRATION, character_id="narrator")],
                narrator_registry,
            )
            MockParser.return_value = mock_parser_instance

            # Act
            book = workflow.run(passage=passage)

        # Assert
        assert book.metadata.title == "Test Book"
        assert book.metadata.author == "Test Author"

    def test_run_returns_book_with_correct_chapter(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            mock_parser_instance = MagicMock()
            narrator_registry = CharacterRegistry.with_default_narrator()
            mock_parser_instance.parse.return_value = (
                [Segment(text="p", segment_type=SegmentType.NARRATION, character_id="narrator")],
                narrator_registry,
            )
            MockParser.return_value = mock_parser_instance

            # Act
            book = workflow.run(passage=passage)

        # Assert
        assert book.content.chapters[0].number == 3


# ---------------------------------------------------------------------------
# Pre-baked synthetic sections
# ---------------------------------------------------------------------------


class TestSyntheticSectionInjection:
    """Verify that book_title and chapter_announcement sections are pre-baked in the Book."""

    def test_book_title_section_is_first(self) -> None:
        # Arrange
        book = _make_book()

        # Act
        first_section = book.content.chapters[0].sections[0]

        # Assert
        assert first_section.section_type == "book_title"

    def test_chapter_announcement_section_is_second(self) -> None:
        # Arrange
        book = _make_book()

        # Act
        second_section = book.content.chapters[0].sections[1]

        # Assert
        assert second_section.section_type == "chapter_announcement"

    def test_book_title_section_has_resolved_segments(self) -> None:
        # Arrange
        book = _make_book()

        # Act
        first_section = book.content.chapters[0].sections[0]

        # Assert
        assert first_section.segments is not None
        assert len(first_section.segments) == 1
        assert first_section.segments[0].segment_type == SegmentType.BOOK_TITLE
        assert first_section.segments[0].character_id == "narrator"

    def test_chapter_announcement_section_has_resolved_segments(self) -> None:
        # Arrange
        book = _make_book()

        # Act
        second_section = book.content.chapters[0].sections[1]

        # Assert
        assert second_section.segments is not None
        assert len(second_section.segments) == 1
        assert second_section.segments[0].segment_type == SegmentType.CHAPTER_ANNOUNCEMENT
        assert second_section.segments[0].character_id == "narrator"


# ---------------------------------------------------------------------------
# AI segmentation skips pre-resolved sections
# ---------------------------------------------------------------------------


class TestSegmentationLoop:
    """Verify the AI segmentation loop skips sections with segments already set."""

    def test_parser_not_called_for_synthetic_sections(self, tmp_path: Path) -> None:
        # Arrange — _make_book() prepends 2 synthetic sections + 2 content sections
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            mock_parser_instance = MagicMock()
            narrator_registry = CharacterRegistry.with_default_narrator()
            mock_parser_instance.parse.return_value = (
                [Segment(text="p", segment_type=SegmentType.NARRATION, character_id="narrator")],
                narrator_registry,
            )
            MockParser.return_value = mock_parser_instance

            # Act
            workflow.run(passage=passage)

        # Assert — parse called for 2 content sections only, not the 2 pre-baked synthetic ones
        assert mock_parser_instance.parse.call_count == 2


# ---------------------------------------------------------------------------
# Audio synthesis
# ---------------------------------------------------------------------------


class TestAudioSynthesis:
    """Verify AudioOrchestrator.synthesize_chapter is called for each chapter."""

    def test_synthesize_chapter_called_once_for_single_chapter(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator") as MockOrchestrator:
            mock_parser_instance = MagicMock()
            narrator_registry = CharacterRegistry.with_default_narrator()
            mock_parser_instance.parse.return_value = (
                [Segment(text="p", segment_type=SegmentType.NARRATION, character_id="narrator")],
                narrator_registry,
            )
            MockParser.return_value = mock_parser_instance

            mock_orch_instance = MagicMock()
            MockOrchestrator.return_value = mock_orch_instance

            # Act
            workflow.run(passage=passage)

        # Assert
        mock_orch_instance.synthesize_chapter.assert_called_once()


# ---------------------------------------------------------------------------
# Factory method
# ---------------------------------------------------------------------------


class TestCreateFactory:
    """Verify ListeningEvalWorkflow.create() wires all production dependencies."""

    def test_create_wires_aws_bedrock_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        from src.config import reload_config

        monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("STABILITY_API_KEY", "test-stability-key")
        monkeypatch.setenv("SUNO_API_KEY", "test-suno-key")
        reload_config()

        with patch("src.workflows.listening_eval_workflow.AWSBedrockProvider") as MockBedrock, \
             patch("src.workflows.listening_eval_workflow.FishAudioTTSProvider") as MockFish, \
             patch("src.workflows.listening_eval_workflow.StableAudioSoundEffectProvider"), \
             patch("src.workflows.listening_eval_workflow.StableAudioAmbientProvider"):
            mock_fish_instance = MagicMock()
            mock_fish_instance.get_voices.return_value = [
                {"voice_id": "v1", "name": "Voice 1", "labels": {}}
            ]
            MockFish.return_value = mock_fish_instance
            MockBedrock.return_value = MagicMock()

            # Act
            workflow = ListeningEvalWorkflow.create()

        # Assert
        MockBedrock.assert_called_once()
        assert workflow._ai_provider == MockBedrock.return_value

    def test_create_raises_without_stability_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        from src.config import reload_config

        monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("STABILITY_API_KEY", raising=False)
        reload_config()

        with patch("src.workflows.listening_eval_workflow.AWSBedrockProvider"), \
             patch("src.workflows.listening_eval_workflow.FishAudioTTSProvider") as MockFish:
            mock_fish_instance = MagicMock()
            mock_fish_instance.get_voices.return_value = [
                {"voice_id": "v1", "name": "Voice 1", "labels": {}}
            ]
            MockFish.return_value = mock_fish_instance

            # Act & Assert
            with pytest.raises(ValueError, match="STABILITY_API_KEY"):
                ListeningEvalWorkflow.create()
