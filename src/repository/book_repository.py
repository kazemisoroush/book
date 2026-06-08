"""Abstract interface for persisting and retrieving parsed Book models.

The ``BookRepository`` defines the contract for storing a fully-parsed
``Book`` to a durable backend. Concrete implementations decide the storage
mechanism (filesystem, database, etc.).  Callers depend only on this
abstraction, keeping the workflow layer decoupled from storage details.

Two distinct snapshots are persisted:

* **input**: the Book after download/parse, before any LLM beat extraction.
  Read via :meth:`load_input`, written via :meth:`save_input`.
* **output**: the Book after AI parsing, with beats. Read via :meth:`load`,
  written via :meth:`save`.
"""
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
