"""Tests for SfxWorkflow."""
from pathlib import Path
from unittest.mock import Mock, patch

from src.workflows.sfx_workflow import SfxWorkflow
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
    Segment,
    SegmentType,
)


class TestSfxWorkflowConstructor:
    """Test SfxWorkflow accepts provider and books_dir."""

    def test_accepts_provider_and_books_dir(self) -> None:
        """SfxWorkflow constructor accepts SoundEffectProvider and books_dir."""
        # Arrange
        mock_provider = Mock()
        mock_repository = Mock()
        books_dir = Path("/tmp/books")

        # Act
        workflow = SfxWorkflow(
            provider=mock_provider,
            repository=mock_repository,
            books_dir=books_dir,
        )

        # Assert
        assert workflow._provider == mock_provider
        assert workflow._books_dir == books_dir


class TestSfxWorkflowCreate:
    """Test SfxWorkflow.create() factory."""

    def test_create_instantiates_provider(self) -> None:
        """create() reads STABILITY_API_KEY and instantiates StableAudioSoundEffectProvider."""
        # Arrange
        mock_config = Mock()
        mock_config.stability_api_key = "test-key"

        # Act
        with patch("src.workflows.sfx_workflow.get_config", return_value=mock_config):
            workflow = SfxWorkflow.create()

        # Assert
        assert workflow._books_dir == Path("books")


class TestSfxWorkflowRun:
    """Tests for SfxWorkflow.run method."""

    def test_calls_provider_generate_for_sound_effect_segments(self) -> None:
        """run() calls provider.generate() for SOUND_EFFECT segments."""
        # Arrange
        mock_provider = Mock()
        mock_provider.generate.return_value = Path("/fake/sfx.mp3")

        mock_repository = Mock()

        segment = Segment(
            text="door knock",
            segment_type=SegmentType.SOUND_EFFECT,
            duration_seconds=2.0,
        )
        section = Section(text="door knock", segments=[segment])
        chapter = Chapter(number=1, title="Chapter 1", sections=[section])
        book = Book(
            metadata=BookMetadata(
                title="Test Book",
                author="Test Author",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[chapter]),
        )
        mock_repository.load.return_value = book

        with patch("src.workflows.sfx_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = SfxWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][0] == "door knock"  # description
        assert call_args[1]["duration_seconds"] == 2.0

    def test_stores_generated_path_in_segment_audio_path(self) -> None:
        """run() stores generated path in segment.audio_path."""
        # Arrange
        generated_path = Path("/tmp/books/123/audio/sfx/seg_001.mp3")
        mock_provider = Mock()
        mock_provider.generate.return_value = generated_path

        mock_repository = Mock()

        segment = Segment(
            text="door knock",
            segment_type=SegmentType.SOUND_EFFECT,
            duration_seconds=2.0,
        )
        section = Section(text="door knock", segments=[segment])
        chapter = Chapter(number=1, title="Chapter 1", sections=[section])
        book = Book(
            metadata=BookMetadata(
                title="Test Book",
                author="Test Author",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[chapter]),
        )
        mock_repository.load.return_value = book

        with patch("src.workflows.sfx_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = SfxWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            result = workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        segments = result.content.chapters[0].sections[0].segments
        assert segments is not None
        assert segments[0].audio_path == str(generated_path)

    def test_processes_vocal_effect_segments(self) -> None:
        """run() processes VOCAL_EFFECT segments."""
        # Arrange
        mock_provider = Mock()
        mock_provider.generate.return_value = Path("/fake/vocal.mp3")

        mock_repository = Mock()

        segment = Segment(
            text="sigh",
            segment_type=SegmentType.VOCAL_EFFECT,
            duration_seconds=2.0,
        )
        section = Section(text="sigh", segments=[segment])
        chapter = Chapter(number=1, title="Chapter 1", sections=[section])
        book = Book(
            metadata=BookMetadata(
                title="Test Book",
                author="Test Author",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[chapter]),
        )
        mock_repository.load.return_value = book

        with patch("src.workflows.sfx_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = SfxWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][0] == "sigh"
