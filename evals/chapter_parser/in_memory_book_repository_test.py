"""Tests for InMemoryBookRepository."""
from evals.chapter_parser.in_memory_book_repository import InMemoryBookRepository
from src.domain.models import Book, BookContent, BookMetadata


def _make_book() -> Book:
    metadata = BookMetadata(
        title="T", author="A", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    return Book(metadata=metadata, content=BookContent(chapters=[]))


def test_save_then_load_returns_same_book() -> None:
    # Arrange
    repo = InMemoryBookRepository()
    book = _make_book()

    # Act
    repo.save(book)

    # Assert
    assert repo.load(book.book_id) is book
    assert repo.exists(book.book_id) is True


def test_load_missing_returns_none() -> None:
    # Arrange
    repo = InMemoryBookRepository()

    # Act / Assert
    assert repo.load("nope") is None
    assert repo.exists("nope") is False
