"""Audio mixing workflow for staged pipeline (stub)."""
from pathlib import Path

import structlog

from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class MixWorkflow(Workflow):
    """Stub workflow for audio mixing — deferred to a future PR."""

    def __init__(
        self,
        repository: BookRepository,
        books_dir: Path = Path("books"),
    ) -> None:
        self._repository = repository
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "MixWorkflow":
        """Factory that wires production dependencies."""
        repository = FileBookRepository(base_dir=str(books_dir))
        return cls(repository=repository, books_dir=books_dir)

    def run(self, request: WorkflowRequest) -> Book:
        """Load book, log not-implemented, save, return.

        Returns:
            The book unchanged.
        """
        book_id = get_book_id_from_url(request.url)
        logger.info("mix_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run all prior workflows first."
            )

        logger.info("mix_workflow_not_implemented", book_id=book_id)

        self._repository.save(book, book_id)
        logger.info("mix_workflow_complete", book_id=book_id)

        return book
