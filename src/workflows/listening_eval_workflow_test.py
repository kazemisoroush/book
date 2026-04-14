"""Tests for ListeningEvalWorkflow — the golden-passage-based eval workflow.

Coverage:
- Book construction from a GoldenE2EPassage (metadata + chapter + sections)
- Synthetic sections (book_title + chapter_announcement) built from passage fields
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
    CharacterRegistry,
    Segment,
    SegmentType,
)
from src.workflows.listening_eval_workflow import GoldenE2EPassage, ListeningEvalWorkflow


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
        book_title_announcement="Test Book, by Test Author.",
        chapter_announcement="Chapter 3. Test Chapter.",
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


def _stub_parser(mock_cls: MagicMock) -> MagicMock:
    """Configure a mock AISectionParser that returns a narration segment."""
    instance = MagicMock()
    registry = CharacterRegistry.with_default_narrator()
    instance.parse.return_value = (
        [Segment(text="p", segment_type=SegmentType.NARRATION, character_id="narrator")],
        registry,
    )
    mock_cls.return_value = instance
    return instance


# ---------------------------------------------------------------------------
# Book construction from passage
# ---------------------------------------------------------------------------


class TestBookConstruction:
    """Verify the Book is built correctly from a GoldenE2EPassage."""

    def test_book_metadata_title_matches_passage(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            _stub_parser(MockParser)

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
            _stub_parser(MockParser)

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
            _stub_parser(MockParser)

            # Act
            book = workflow.run(passage=passage)

        # Assert
        assert book.content.chapters[0].number == 3


# ---------------------------------------------------------------------------
# Synthetic sections from passage fields
# ---------------------------------------------------------------------------


class TestSyntheticSections:
    """Verify book_title and chapter_announcement sections are built from passage."""

    def test_first_section_is_book_title(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            _stub_parser(MockParser)

            # Act
            book = workflow.run(passage=passage)

        # Assert
        first = book.content.chapters[0].sections[0]
        assert first.section_type == "book_title"
        assert first.text == "Test Book, by Test Author."

    def test_second_section_is_chapter_announcement(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            _stub_parser(MockParser)

            # Act
            book = workflow.run(passage=passage)

        # Assert
        second = book.content.chapters[0].sections[1]
        assert second.section_type == "chapter_announcement"
        assert second.text == "Chapter 3. Test Chapter."


# ---------------------------------------------------------------------------
# AI segmentation skips pre-resolved sections
# ---------------------------------------------------------------------------


class TestSegmentationLoop:
    """Verify the AI segmentation loop skips sections with segments already set."""

    def test_parser_only_called_for_content_sections(self, tmp_path: Path) -> None:
        # Arrange
        passage = _minimal_passage()
        workflow, _, _ = _make_workflow(tmp_path)

        with patch("src.workflows.listening_eval_workflow.AISectionParser") as MockParser, \
             patch("src.workflows.listening_eval_workflow.AudioOrchestrator"):
            mock_parser = _stub_parser(MockParser)

            # Act
            workflow.run(passage=passage)

        # Assert — 2 content sections parsed, 2 synthetic sections skipped
        assert mock_parser.parse.call_count == 2


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
            _stub_parser(MockParser)
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
