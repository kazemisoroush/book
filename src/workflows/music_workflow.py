"""Music generation workflow for staged pipeline (stub)."""
from pathlib import Path

import structlog

from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.project_gutenberg_url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class MusicWorkflow(Workflow):
    """Stub workflow for music generation — deferred to a future PR."""

    def __init__(
        self,
        repositories: list[BookRepository],
        books_dir: Path = Path("books"),
    ) -> None:
        self._repositories = repositories
        self._books_dir = books_dir

    def run(self, request: WorkflowRequest) -> Book:
        """Load book, log not-implemented, save, return.

        Returns:
            The book unchanged.
        """
        book_id = get_book_id_from_url(request.url)
        logger.info("music_workflow_started", book_id=book_id)

        book = self._repositories[0].load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in store for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )

        logger.info("music_workflow_not_implemented", book_id=book_id)

        for store in self._repositories:
            store.save(book)
        logger.info("music_workflow_complete", book_id=book_id)

        return book
