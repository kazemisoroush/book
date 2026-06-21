"""Abstract interface for obtaining a parsed Book from a source URL."""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import BookParseContext


class BookSource(ABC):
    """Abstract base class for book sources."""

    @abstractmethod
    def get_book(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> BookParseContext:
        """Return a BookParseContext ready for the AI beatation loop."""
