"""Abstract interface for parsing book content (chapters and sections).

Defines the BookContentParser ABC that all concrete content parsers must implement.
Content parsing extracts the structural elements of a book: chapters, sections, paragraphs.
"""
from abc import ABC, abstractmethod

from src.domain.models import BookContent


class BookContentParser(ABC):
    """Abstract base class for book content parsers.

    Concrete implementations extract structured content (chapters, sections)
    from downloaded book data in various formats (HTML, EPUB, PDF, etc.).
    """

    @abstractmethod
    def parse(self, content: str) -> BookContent:
        """Parse content structure from the given content string.

        Args:
            content: Raw book content (HTML, text, etc.).

        Returns:
            Structured BookContent object with chapters and sections.

        Raises:
            RuntimeError: If parsing fails.
        """
