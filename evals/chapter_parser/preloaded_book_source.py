"""BookSource that hands a pre-loaded Book straight to the workflow."""
import copy
from typing import Optional

from src.domain.models import Book, BookParseContext
from src.parsers.book_source import BookSource


class PreloadedBookSource(BookSource):
    """Expose an already-constructed Book as a BookSource."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def get_book(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> BookParseContext:
        book = copy.deepcopy(self._book)
        return BookParseContext(
            book=book,
            chapters_to_parse=list(book.content.chapters),
            content=book.content,
        )
