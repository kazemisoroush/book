"""Abstract interface for persisting and retrieving parsed Book models.

The ``BookRepository`` defines the contract for storing a fully-parsed
``Book`` to a durable backend. Concrete implementations decide the storage
mechanism (filesystem, database, etc.).  Callers depend only on this
abstraction, keeping the workflow layer decoupled from storage details.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import Book


class BookRepository(ABC):
    """Abstract base class for book persistence."""

    @abstractmethod
    def save(self, book: Book) -> None:
        """Persist *book* under :attr:`Book.book_id`.

        If an entry already exists for that id, it is overwritten.
        """

    @abstractmethod
    def load(self, book_id: str) -> Optional[Book]:
        """Load a previously saved book by *book_id*.

        Returns ``None`` if no entry exists for *book_id*.
        """

    @abstractmethod
    def exists(self, book_id: str) -> bool:
        """Return ``True`` if a saved book exists for *book_id*."""
