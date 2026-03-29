"""Workflow interface for book processing pipelines."""
from abc import ABC, abstractmethod
from src.domain.models import Book


class Workflow(ABC):
    """Abstract workflow interface.

    A workflow orchestrates multiple components to process a book
    from a URL to a fully populated ``Book``.

    All concrete workflows return a ``Book``.  Any workflow-specific
    data (e.g. ``CharacterRegistry``) is carried as a field on the
    returned ``Book`` instance.

    The default ``chapter_limit=3`` is intentional: it prevents
    accidental full-book AI/TTS runs that incur large API costs.
    Callers must pass ``chapter_limit=0`` explicitly to mean "all
    chapters".
    """

    @abstractmethod
    def run(self, url: str, chapter_limit: int = 3) -> Book:
        """Run the workflow with the given URL.

        Args:
            url: Project Gutenberg book URL (or equivalent source URL)
            chapter_limit: Maximum number of chapters to process.
                           ``0`` means all chapters.  Defaults to 3.

        Returns:
            A fully populated Book instance

        Raises:
            Exception: If the workflow fails
        """
        pass
