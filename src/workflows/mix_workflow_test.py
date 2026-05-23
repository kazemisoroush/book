"""Tests for MixWorkflow (stub)."""
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
from src.workflows.mix_workflow import MixWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.mix_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _make_book() -> Book:
    return Book(
        metadata=BookMetadata(
            title="Mix Book", author="Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Ch1", sections=[Section(text="test")])
        ]),
    )


def test_run_loads_and_saves_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stub MixWorkflow loads book and saves it back unchanged."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)
    _patch_resolver(monkeypatch, book_id)

    workflow = MixWorkflow(repository=repository, books_dir=tmp_path)

    # Act
    result = workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert result.metadata.title == "Mix Book"
    loaded = repository.load(book_id)
    assert loaded is not None


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run() raises ValueError when book_id not found."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent")
    workflow = MixWorkflow(repository=repository, books_dir=tmp_path)

    # Act & Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))
