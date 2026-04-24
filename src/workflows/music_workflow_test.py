"""Tests for MusicWorkflow (stub)."""
from pathlib import Path

import pytest

from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.workflows.music_workflow import MusicWorkflow


def _make_book() -> Book:
    return Book(
        metadata=BookMetadata(
            title="Music Book", author="Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Ch1", sections=[Section(text="test")])
        ]),
    )


def test_run_loads_and_saves_book(tmp_path: Path) -> None:
    """Stub MusicWorkflow loads book and saves it back unchanged."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    workflow = MusicWorkflow(repository=repository, books_dir=tmp_path)

    # Act
    result = workflow.run(book_id=book_id)

    # Assert
    assert result.metadata.title == "Music Book"
    loaded = repository.load(book_id)
    assert loaded is not None


def test_run_raises_when_book_not_found(tmp_path: Path) -> None:
    """run() raises ValueError when book_id not found."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    workflow = MusicWorkflow(repository=repository, books_dir=tmp_path)

    # Act & Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(book_id="nonexistent")
