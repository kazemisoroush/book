"""Workflow interface for book processing pipelines."""
from abc import ABC, abstractmethod
from typing import Optional
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

    New parameters (start_chapter, end_chapter) are supported for workflows
    that implement incremental parsing with caching. Workflows that don't
    support these parameters should ignore them.
    """

    @abstractmethod
    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        chapter_limit: int = 3,
        reparse: bool = False,
    ) -> Book:
        """Run the workflow with the given URL.

        Args:
            url: Project Gutenberg book URL (or equivalent source URL)
            start_chapter: 1-based chapter index to begin parsing (default: 1).
                          For workflows with caching, if 1 and a cached partial
                          book exists, auto-resumes from the last cached chapter.
            end_chapter: 1-based chapter index to end parsing (inclusive).
                        Default: None (parse all chapters in the book).
            chapter_limit: Maximum number of chapters to process (for backward
                          compatibility). ``0`` means all chapters. Defaults to 3.
                          If end_chapter is None and chapter_limit > 0, end_chapter
                          is set to chapter_limit.
            reparse: When ``True``, bypass the cache and run the full parse
                    pipeline. Defaults to ``False``. Only used by workflows with
                    caching support.

        Returns:
            A fully populated Book instance

        Raises:
            Exception: If the workflow fails
        """
        pass
