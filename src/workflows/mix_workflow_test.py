"""Tests for MixWorkflow."""
from pathlib import Path
from unittest.mock import Mock, patch

from src.workflows.mix_workflow import MixWorkflow
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)


class TestMixWorkflowConstructor:
    """Test MixWorkflow accepts books_dir."""

    def test_accepts_books_dir(self) -> None:
        """MixWorkflow constructor accepts books_dir."""
        # Arrange
        mock_repository = Mock()
        books_dir = Path("/tmp/books")

        # Act
        workflow = MixWorkflow(
            repository=mock_repository,
            books_dir=books_dir,
        )

        # Assert
        assert workflow._books_dir == books_dir


class TestMixWorkflowRun:
    """Tests for MixWorkflow.run method."""

    def test_run_loads_and_saves_book(self) -> None:
        """run() loads book from repository and saves it back."""
        # Arrange
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

        with patch("src.workflows.mix_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = MixWorkflow(
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        mock_repository.load.assert_called_once_with("123")
        mock_repository.save.assert_called_once()
