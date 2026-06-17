"""Abstract interface for persisting input and output snapshots of a Book."""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import Book, Chapter


class BookStore(ABC):
    """Abstract base class for book persistence."""

    @abstractmethod
    def save(self, book: Book) -> None:
        """Persist *book* as the output snapshot under :attr:`Book.book_id`."""

    @abstractmethod
    def save_chapter(self, book: Book, chapter: Chapter) -> None:
        """Persist *chapter* of *book*.

        Called once per parsed chapter by the AI workflow. Backends that hold
        full-book state (e.g. file JSON) typically delegate to :meth:`save`.
        Backends that store per-chapter content (e.g. ElevenLabs Studio) use
        the chapter as the unit of update.
        """

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
