"""Tests for MusicWorkflow."""
from pathlib import Path
from unittest.mock import Mock, patch

from src.workflows.music_workflow import MusicWorkflow
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)


class TestMusicWorkflowConstructor:
    """Test MusicWorkflow accepts provider and books_dir."""

    def test_accepts_provider_and_books_dir(self) -> None:
        """MusicWorkflow constructor accepts MusicProvider and books_dir."""
        # Arrange
        mock_provider = Mock()
        mock_repository = Mock()
        books_dir = Path("/tmp/books")

        # Act
        workflow = MusicWorkflow(
            provider=mock_provider,
            repository=mock_repository,
            books_dir=books_dir,
        )

        # Assert
        assert workflow._provider == mock_provider
        assert workflow._books_dir == books_dir


class TestMusicWorkflowCreate:
    """Test MusicWorkflow.create() factory."""

    def test_create_instantiates_provider(self) -> None:
        """create() reads SUNO_API_KEY and instantiates SunoMusicProvider."""
        # Arrange
        mock_config = Mock()
        mock_config.suno_api_key = "test-key"

        # Act
        with patch("src.workflows.music_workflow.get_config", return_value=mock_config):
            workflow = MusicWorkflow.create()

        # Assert
        assert workflow._books_dir == Path("books")


class TestMusicWorkflowRun:
    """Tests for MusicWorkflow.run method."""

    def test_calls_provider_generate_for_each_chapter(self) -> None:
        """run() calls provider.generate() for each chapter."""
        # Arrange
        mock_provider = Mock()
        mock_provider.generate.return_value = Path("/fake/music.mp3")

        mock_repository = Mock()

        section = Section(text="Test")
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

        with patch("src.workflows.music_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = MusicWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        mock_provider.generate.assert_called_once()

    def test_stores_generated_paths_in_chapter_music_audio_paths(self) -> None:
        """run() stores generated paths in chapter.music_audio_paths."""
        # Arrange
        generated_path = Path("/tmp/books/123/audio/music/ch_01.mp3")
        mock_provider = Mock()
        mock_provider.generate.return_value = generated_path

        mock_repository = Mock()

        section = Section(text="Test")
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

        with patch("src.workflows.music_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = MusicWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            result = workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        assert len(result.content.chapters[0].music_audio_paths) == 1
        assert result.content.chapters[0].music_audio_paths[0] == str(generated_path)
