"""Interface for book parsers."""
from abc import ABC, abstractmethod
from src.domain.models import Book


class BookParser(ABC):
    """Abstract base class for book parsers."""

    @abstractmethod
    def parse(self, file_path: str) -> Book:
        """Parse a book file and return a Book object."""
        pass
