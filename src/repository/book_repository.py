"""Abstract interface for persisting input and output snapshots of a Book."""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import Book


class BookRepository(ABC):
    """Abstract base class for book persistence."""

    @abstractmethod
    def save(self, book: Book) -> None:
        """Persist *book* as the output snapshot under :attr:`Book.book_id`."""

    @abstractmethod
    def load(self, book_id: str) -> Optional[Book]:
        """Load the output snapshot for *book_id*, or ``None`` if missing."""

    @abstractmethod
    def exists(self, book_id: str) -> bool:
        """Return ``True`` if an output snapshot exists for *book_id*."""

    @abstractmethod
    def save_input(self, book: Book) -> None:
        """Persist *book* as the input snapshot (post-parse, pre-AI)."""

    @abstractmethod
    def load_input(self, book_id: str) -> Optional[Book]:
        """Load the input snapshot for *book_id*, or ``None`` if missing."""
