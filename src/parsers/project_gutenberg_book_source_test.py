"""Unit tests for ProjectGutenbergBookSource."""
from typing import Optional

from src.domain.beat import Beat, BeatType
from src.domain.character import make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
from src.repository.book_repository import BookRepository


def _default_metadata() -> BookMetadata:
    return BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )


class _FakeDownloader:
    """Stub downloader that returns pre-set HTML."""

    def __init__(self, html: str = "<html></html>") -> None:
        self._html = html
        self.download_calls: list[str] = []

    def download(self, url: str) -> str:
        self.download_calls.append(url)
        return self._html


class _FakeMetadataParser:
    def parse(self, content: str) -> BookMetadata:
        return _default_metadata()


class _FakeContentParser:
    def __init__(self, chapters: list[Chapter]) -> None:
        self._chapters = chapters

    def parse(self, content: str) -> BookContent:
        return BookContent(chapters=self._chapters)


class _FakeRepository(BookRepository):
    def __init__(self, stored: Optional[Book] = None) -> None:
        self._store: dict[str, Book] = {}
        self._inputs: dict[str, Book] = {}
        self._default = stored

    def save(self, book: Book) -> None:
        self._store[book.book_id] = book

    def save_chapter(self, book: Book, chapter: Chapter) -> None:
        del chapter
        self._store[book.book_id] = book

    def load(self, book_id: str) -> Optional[Book]:
        if book_id in self._store:
            return self._store[book_id]
        return self._default

    def exists(self, book_id: str) -> bool:
        return book_id in self._store or self._default is not None

    def save_input(self, book: Book) -> None:
        self._inputs[book.book_id] = book

    def load_input(self, book_id: str) -> Optional[Book]:
        return self._inputs.get(book_id)


class TestGetBook:
    """get_book returns a BookParseContext ready for AI."""

    def test_no_cache_returns_all_chapters_to_parse(self) -> None:
        # Arrange
        chapters = [
            Chapter(number=i, title=f"Ch {i}", sections=[Section(text=f"Text {i}.")])
            for i in range(1, 4)
        ]
        source = ProjectGutenbergBookSource(
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            metadata_parser=_FakeMetadataParser(),  # type: ignore[arg-type]
            content_parser=_FakeContentParser(chapters),  # type: ignore[arg-type]
        )

        # Act
        ctx = source.get_book("http://example.com/test", start_chapter=1, end_chapter=3)

        # Assert
        assert len(ctx.chapters_to_parse) == 3
        assert len(ctx.content.chapters) == 3
        assert len(ctx.book.content.chapters) == 0  # Empty book, no cache

    def test_cached_book_skips_cached_chapters(self) -> None:
        # Arrange — cached book has chapters 1-2
        cached_chapters = [
            Chapter(
                number=i, title=f"Ch {i}",
                sections=[Section(text=f"Cached {i}.")],
                beats=[Beat(text=f"Cached {i}.", beat_type=BeatType.NARRATION, character_id=1)],
            )
            for i in range(1, 3)
        ]
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=cached_chapters),
            character_registry=CharacterRegistry(characters=[make_default_narrator()]),
        )
        repo = _FakeRepository(stored=cached_book)

        all_chapters = [
            Chapter(number=i, title=f"Ch {i}", sections=[Section(text=f"Text {i}.")])
            for i in range(1, 6)
        ]
        source = ProjectGutenbergBookSource(
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            metadata_parser=_FakeMetadataParser(),  # type: ignore[arg-type]
            content_parser=_FakeContentParser(all_chapters),  # type: ignore[arg-type]
            repository=repo,
        )

        # Act
        ctx = source.get_book("http://example.com/test", start_chapter=1, end_chapter=5)

        # Assert — only chapters 3-5 need parsing
        assert len(ctx.chapters_to_parse) == 3
        assert [ch.number for ch in ctx.chapters_to_parse] == [3, 4, 5]
        # The book is the cached one with chapters 1-2
        assert len(ctx.book.content.chapters) == 2

    def test_refresh_ignores_cache(self) -> None:
        # Arrange — cached book exists but refresh=True
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=[
                Chapter(number=1, title="Ch 1", sections=[Section(text="Cached.")]),
            ]),
            character_registry=CharacterRegistry(characters=[make_default_narrator()]),
        )
        repo = _FakeRepository(stored=cached_book)

        all_chapters = [
            Chapter(number=i, title=f"Ch {i}", sections=[Section(text=f"Text {i}.")])
            for i in range(1, 4)
        ]
        source = ProjectGutenbergBookSource(
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            metadata_parser=_FakeMetadataParser(),  # type: ignore[arg-type]
            content_parser=_FakeContentParser(all_chapters),  # type: ignore[arg-type]
            repository=repo,
        )

        # Act
        ctx = source.get_book(
            "http://example.com/test", start_chapter=1, end_chapter=3, refresh=True,
        )

        # Assert — all chapters need parsing (cache bypassed)
        assert len(ctx.chapters_to_parse) == 3
        assert len(ctx.book.content.chapters) == 0  # Fresh book

    def test_save_input_called_after_parse_when_no_output_cache(self) -> None:
        # Arrange
        chapters = [
            Chapter(number=1, title="Ch 1", sections=[Section(text="Hello.")]),
        ]
        repo = _FakeRepository()
        source = ProjectGutenbergBookSource(
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            metadata_parser=_FakeMetadataParser(),  # type: ignore[arg-type]
            content_parser=_FakeContentParser(chapters),  # type: ignore[arg-type]
            repository=repo,
        )

        # Act
        source.get_book("http://example.com/test")

        # Assert
        input_snapshot = repo.load_input(_default_metadata().book_id)
        assert input_snapshot is not None
        assert [c.number for c in input_snapshot.content.chapters] == [1]

    def test_save_input_skipped_when_resuming_from_output(self) -> None:
        # Arrange — output cache present, so save_input should not run
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=[
                Chapter(number=1, title="Ch 1", sections=[Section(text="Cached.")]),
            ]),
            character_registry=CharacterRegistry(characters=[make_default_narrator()]),
        )
        repo = _FakeRepository(stored=cached_book)
        source = ProjectGutenbergBookSource(
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            metadata_parser=_FakeMetadataParser(),  # type: ignore[arg-type]
            content_parser=_FakeContentParser([cached_book.content.chapters[0]]),  # type: ignore[arg-type]
            repository=repo,
        )

        # Act
        source.get_book("http://example.com/test")

        # Assert
        assert repo.load_input(_default_metadata().book_id) is None

    def test_start_end_chapter_filters_correctly(self) -> None:
        # Arrange — 10 chapters, request 5-8
        all_chapters = [
            Chapter(number=i, title=f"Ch {i}", sections=[Section(text=f"Text {i}.")])
            for i in range(1, 11)
        ]
        source = ProjectGutenbergBookSource(
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            metadata_parser=_FakeMetadataParser(),  # type: ignore[arg-type]
            content_parser=_FakeContentParser(all_chapters),  # type: ignore[arg-type]
        )

        # Act
        ctx = source.get_book("http://example.com/test", start_chapter=5, end_chapter=8)

        # Assert
        assert len(ctx.chapters_to_parse) == 4
        assert [ch.number for ch in ctx.chapters_to_parse] == [5, 6, 7, 8]
