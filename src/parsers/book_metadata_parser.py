"""Abstract interface for parsing book metadata from downloaded content.

Defines the BookMetadataParser ABC that all concrete metadata parsers must implement.
Metadata includes title, author, publication date, language, and other bibliographic info.
"""
from abc import ABC, abstractmethod

from src.domain.models import BookMetadata


class BookMetadataParser(ABC):
    """Abstract base class for book metadata parsers.

    Concrete implementations extract structured metadata (title, author, etc.)
    from downloaded content in various formats (HTML, EPUB, PDF, etc.).
    """

    @abstractmethod
    def parse(self, content: str) -> BookMetadata:
        """Parse metadata from the given content string.

        Args:
            content: Raw book content (HTML, text, etc.).

        Returns:
            Structured BookMetadata object.

        Raises:
            RuntimeError: If parsing fails.
        """
