"""Tests for AmbientWorkflow."""
from unittest.mock import Mock, patch
from src.workflows.ambient_workflow import AmbientWorkflow
from src.domain.models import Book, BookMetadata, BookContent
from src.repository.book_repository import BookRepository


class TestAmbientWorkflowRun:
    """Tests for AmbientWorkflow.run method."""

    def test_run_loads_and_saves_book_via_repository(self) -> None:
        """AmbientWorkflow.run() loads book from repository and saves it back."""
        # Arrange
        url = "https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip"
        mock_repository = Mock(spec=BookRepository)
        mock_book = Book(
            metadata=BookMetadata(
                title="Pride and Prejudice",
                author="Jane Austen",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[]),
        )
        mock_repository.load.return_value = mock_book

        # Mock the URL mapper to avoid actual HTTP calls
        with patch('src.workflows.ambient_workflow.get_book_id_from_url') as mock_mapper:
            mock_mapper.return_value = "Pride and Prejudice - Jane Austen"

            workflow = AmbientWorkflow(repository=mock_repository)

            # Act
            result = workflow.run(url)

        # Assert
        assert result == mock_book
        mock_repository.load.assert_called_once_with("Pride and Prejudice - Jane Austen")
        mock_repository.save.assert_called_once()
        saved_book, saved_book_id = mock_repository.save.call_args[0]
        assert saved_book == mock_book
        assert saved_book_id == "Pride and Prejudice - Jane Austen"

    def test_run_returns_book(self) -> None:
        """AmbientWorkflow.run() returns the processed book."""
        # Arrange
        url = "https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip"
        mock_repository = Mock(spec=BookRepository)
        mock_book = Book(
            metadata=BookMetadata(
                title="Test Book",
                author="Test Author",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[]),
        )
        mock_repository.load.return_value = mock_book

        with patch('src.workflows.ambient_workflow.get_book_id_from_url') as mock_mapper:
            mock_mapper.return_value = "Test Book - Test Author"

            workflow = AmbientWorkflow(repository=mock_repository)

            # Act
            result = workflow.run(url)

        # Assert
        assert isinstance(result, Book)
        assert result.metadata.title == "Test Book"
