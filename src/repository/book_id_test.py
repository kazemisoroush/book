"""Unit tests for book_id generation."""
from src.domain.models import BookMetadata
from src.repository.book_id import generate_book_id


class TestGenerateBookId:
    """generate_book_id produces a safe, human-readable directory name."""

    def test_simple_title_and_author(self) -> None:
        """Standard metadata yields 'Title - Author'."""
        # Arrange
        metadata = BookMetadata(
            title="Pride and Prejudice",
            author="Jane Austen",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )

        # Act
        result = generate_book_id(metadata)

        # Assert
        assert result == "Pride and Prejudice - Jane Austen"

    def test_unsafe_characters_are_replaced(self) -> None:
        """Colons, slashes, and backslashes are replaced with dashes."""
        # Arrange
        metadata = BookMetadata(
            title="A Tale: Of Two/Cities",
            author="Charles\\Dickens",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )

        # Act
        result = generate_book_id(metadata)

        # Assert
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result

    def test_missing_author_uses_unknown(self) -> None:
        """When author is None, 'Unknown' is substituted."""
        # Arrange
        metadata = BookMetadata(
            title="Anonymous Work",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )

        # Act
        result = generate_book_id(metadata)

        # Assert
        assert result == "Anonymous Work - Unknown"
