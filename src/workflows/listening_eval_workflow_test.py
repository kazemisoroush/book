"""Tests for ListeningEvalWorkflow — the golden-passage-based eval workflow.

Coverage:
- Book construction from a GoldenE2EPassage (metadata + chapter + sections)
- Synthetic sections (book_title + chapter_announcement) are injected
- AI segmentation loop skips sections with pre-existing segments
- Voice assigner is called with the final character registry
- AudioOrchestrator synthesizes each chapter
- create() factory wires AWSBedrockProvider as ai_provider
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.tts.voice_assigner import VoiceEntry
from src.domain.models import (
    BookMetadata,
    CharacterRegistry,
    Section,
    Segment,
    SegmentType,
)
from src.evals.book.fixtures.golden_e2e_passage import GoldenE2EPassage
from src.workflows.listening_eval_workflow import ListeningEvalWorkflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_passage() -> GoldenE2EPassage:
    """Return a small passage with 2 sections for fast test execution."""
    return GoldenE2EPassage(
        name="test_passage",
        book_title="Test Book",
        author="Test Author",
        gutenberg_url="https://example.com",
        chapter_number=3,
        chapter_title="Test Chapter",
        sections=["First paragraph.", "Second paragraph with dialogue."],
        expected_features=["narration", "dialogue"],
        notes="Test passage",
    )


def _make_workflow(tmp_path: Path) -> tuple[ListeningEvalWorkflow, MagicMock, MagicMock]:
    """Create a ListeningEvalWorkflow with mock ai_provider and tts_provider.

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
        books_dir=tmp_path,
    )
    return workflow, mock_ai_provider, mock_tts_provider


# ---------------------------------------------------------------------------
# Book construction from passage
# ---------------------------------------------------------------------------


class TestBookConstruction:
    """Verify the Book is built correctly from a GoldenE2EPassage."""

    def test_book_metadata_title_matches_passage(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, mock_ai, _ = _make_workflow(tmp_path)

        # Mock AI section parser to return minimal segments
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

    def test_book_metadata_author_matches_passage(self, tmp_path: Path) -> None:
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
        assert book.metadata.author == "Test Author"

    def test_book_chapter_number_matches_passage(self, tmp_path: Path) -> None:
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
# Synthetic section injection
# ---------------------------------------------------------------------------


class TestSyntheticSectionInjection:
    """Verify that book_title and chapter_announcement sections are injected."""

    def test_synthetic_sections_are_injected(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AIProjectGutenbergWorkflow._inject_synthetic_sections") as mock_inject, \
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

        # Assert — _inject_synthetic_sections must be called once
        mock_inject.assert_called_once()

    def test_synthetic_sections_receive_metadata(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        injected_metadata: list[BookMetadata] = []

        def capture_inject(chapters: list, metadata: BookMetadata, formatter: object) -> None:
            injected_metadata.append(metadata)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AIProjectGutenbergWorkflow._inject_synthetic_sections", side_effect=capture_inject), \
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

        # Assert
        assert len(injected_metadata) == 1
        assert injected_metadata[0].title == "Test Book"
        assert injected_metadata[0].author == "Test Author"


# ---------------------------------------------------------------------------
# AI segmentation skips pre-resolved sections
# ---------------------------------------------------------------------------


class TestSegmentationLoop:
    """Verify the AI segmentation loop skips sections with segments already set."""

    def test_parser_not_called_for_synthetic_sections(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        # Pre-inject synthetic sections manually by making _inject_synthetic_sections
        # add sections with segments already populated.
        already_resolved = Section(
            text="Book Title.",
            section_type="book_title",
            segments=[Segment(text="Book Title.", segment_type=SegmentType.BOOK_TITLE, character_id="narrator")],
        )

        def inject_with_resolved(chapters: list, metadata: BookMetadata, formatter: object) -> None:
            # Insert a synthetic section with segments already set
            chapters[0].sections.insert(0, already_resolved)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AIProjectGutenbergWorkflow._inject_synthetic_sections", side_effect=inject_with_resolved), \
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

        # Assert — parse called for 2 real sections only, not the synthetic one
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
             patch("src.workflows.listening_eval_workflow.AIProjectGutenbergWorkflow._inject_synthetic_sections"), \
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
    """Verify ListeningEvalWorkflow.create() wires an AWSBedrockProvider as ai_provider."""

    def test_create_wires_aws_bedrock_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        from src.config import reload_config

        monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        reload_config()

        with patch("src.workflows.listening_eval_workflow.AWSBedrockProvider") as MockBedrock, \
             patch("src.workflows.listening_eval_workflow.FishAudioTTSProvider") as MockFish:
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
