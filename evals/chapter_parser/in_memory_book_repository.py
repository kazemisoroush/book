"""In-memory BookRepository used by the chapter_parser eval."""
from typing import Optional

from src.domain.models import Book
from src.repository.book_repository import BookRepository


class InMemoryBookRepository(BookRepository):
    """Keep saved Books in a dict; nothing touches disk."""

    def __init__(self) -> None:
        self._books: dict[str, Book] = {}

    def save(self, book: Book) -> None:
        self._books[book.book_id] = book

    def load(self, book_id: str) -> Optional[Book]:
        return self._books.get(book_id)

    def exists(self, book_id: str) -> bool:
        return book_id in self._books
