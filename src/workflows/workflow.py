"""Workflow interface for book processing pipelines."""
from abc import ABC, abstractmethod
from typing import Optional
from src.domain.models import Book


class Workflow(ABC):
    """Abstract workflow interface.

    A workflow orchestrates multiple components to process a book.

    URL-based workflows (parse, ai) accept a URL as the identifier.
    Staged workflows (tts, sfx, ambient, music, mix) accept a book_id.

    All concrete workflows return a ``Book``.  Any workflow-specific
    data (e.g. ``CharacterRegistry``) is carried as a field on the
    returned ``Book`` instance.

    Parameters (start_chapter, end_chapter) are supported for workflows
    that implement incremental parsing with caching. Workflows that don't
    support these parameters should ignore them.
    """

    @abstractmethod
    def run(
        self,
        identifier: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Run the workflow with the given identifier.

        Args:
            identifier: Book URL (for parse/ai) or book_id (for staged workflows).
            start_chapter: 1-based chapter index to begin parsing (default: 1).
            end_chapter: 1-based chapter index to end parsing (inclusive).
            refresh: When ``True``, bypass the cache and re-run the pipeline.

        Returns:
            A fully populated Book instance

        Raises:
            Exception: If the workflow fails
        """
        pass
