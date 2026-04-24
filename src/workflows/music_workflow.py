"""Music generation workflow for staged pipeline (stub)."""
from pathlib import Path
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.repository.book_repository import BookRepository

logger = structlog.get_logger(__name__)


class MusicWorkflow(Workflow):
    """Stub workflow for music generation — deferred to a future PR."""

    def __init__(
        self,
        repository: BookRepository,
        books_dir: Path = Path("books"),
    ) -> None:
        self._repository = repository
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "MusicWorkflow":
        """Factory that wires production dependencies."""
        from src.repository.file_book_repository import FileBookRepository

        repository = FileBookRepository(base_dir=str(books_dir))
        return cls(repository=repository, books_dir=books_dir)

    def run(
        self,
        book_id: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Load book, log not-implemented, save, return.

        Args:
            book_id: Repository book identifier.
            start_chapter: Ignored.
            end_chapter: Ignored.
            refresh: Ignored.

        Returns:
            The book unchanged.
        """
        logger.info("music_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )

        logger.info("music_workflow_not_implemented", book_id=book_id)

        self._repository.save(book, book_id)
        logger.info("music_workflow_complete", book_id=book_id)

        return book
