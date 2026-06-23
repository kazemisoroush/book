"""Tests for ParseWorkflow."""
from typing import Optional

from src.domain.character import make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    BookParseContext,
    Chapter,
    Section,
)
from src.parsers.book_source import BookSource
from src.repository.book_repository import BookRepository
from src.workflows.parse_workflow import ParseWorkflow
from src.workflows.workflow import WorkflowRequest


class _PreloadedSource(BookSource):
    def __init__(self, ctx: BookParseContext) -> None:
        self._ctx = ctx
        self.calls: list[str] = []

    def get_book(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> BookParseContext:
        self.calls.append(url)
        return self._ctx


class _RecordingRepository(BookRepository):
    def __init__(self) -> None:
        self.saved_books: list[Book] = []

    def save(self, book: Book) -> None:
        self.saved_books.append(book)

    def save_chapter(self, book: Book, chapter: Chapter) -> None:
        pass

    def load(self, book_id: str) -> Optional[Book]:
        return None

    def exists(self, book_id: str) -> bool:
        return False

    def save_input(self, book: Book) -> None:
        pass

    def load_input(self, book_id: str) -> Optional[Book]:
        return None


def _metadata() -> BookMetadata:
    return BookMetadata(
        title="Frankenstein", author="Mary Shelley",
        releaseDate=None, language=None,
        originalPublication=None, credits=None,
    )


def _context() -> BookParseContext:
    chapters = [
        Chapter(number=1, title="Letter 1", label="Letter 1",
                sections=[Section(text="To Mrs. Saville.")]),
        Chapter(number=2, title="Chapter 1",
                sections=[Section(text="I am by birth a Genevese.")]),
    ]
    content = BookContent(chapters=chapters)
    book = Book(
        metadata=_metadata(),
        content=BookContent(chapters=[]),
        character_registry=CharacterRegistry(characters=[make_default_narrator()]),
    )
    return BookParseContext(
        book=book,
        chapters_to_parse=chapters,
        content=content,
    )


def test_run_calls_book_source_and_saves_to_repositories() -> None:
    # Arrange
    ctx = _context()
    source = _PreloadedSource(ctx)
    repo_a = _RecordingRepository()
    repo_b = _RecordingRepository()
    workflow = ParseWorkflow(book_source=source, repositories=[repo_a, repo_b])

    # Act
    book = workflow.run(WorkflowRequest(url="https://example.com/book.zip"))

    # Assert
    assert source.calls == ["https://example.com/book.zip"]
    assert len(repo_a.saved_books) == 1
    assert len(repo_b.saved_books) == 1


def test_run_returns_book_with_parsed_content() -> None:
    # Arrange
    ctx = _context()
    source = _PreloadedSource(ctx)
    repo = _RecordingRepository()
    workflow = ParseWorkflow(book_source=source, repositories=[repo])

    # Act
    book = workflow.run(WorkflowRequest(url="https://example.com/book.zip"))

    # Assert
    assert book.metadata.title == "Frankenstein"
    assert len(book.content.chapters) == 2
    assert book.content.chapters[0].label == "Letter 1"
    assert book.content.chapters[1].label is None


def test_run_seeds_default_narrator() -> None:
    # Arrange
    ctx = _context()
    source = _PreloadedSource(ctx)
    repo = _RecordingRepository()
    workflow = ParseWorkflow(book_source=source, repositories=[repo])

    # Act
    book = workflow.run(WorkflowRequest(url="https://example.com/book.zip"))

    # Assert
    narrator = book.character_registry.get(1)
    assert narrator is not None
    assert narrator.name == "Narrator"
