"""Tests for PreloadedBookSource."""
from evals.chapter_parser.preloaded_book_source import PreloadedBookSource
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section


def _make_book() -> Book:
    metadata = BookMetadata(
        title="T", author="A", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(
        number=1, title="", sections=[Section(text="hello", section_type="text")],
    )
    return Book(metadata=metadata, content=BookContent(chapters=[chapter]))


def test_get_book_returns_the_preloaded_book() -> None:
    # Arrange
    book = _make_book()
    source = PreloadedBookSource(book)

    # Act
    ctx = source.get_book(url="ignored")

    # Assert
    assert ctx.book is book
    assert ctx.content is book.content
    assert [c.number for c in ctx.chapters_to_parse] == [1]
