"""Music generation workflow for staged pipeline."""
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url

logger = structlog.get_logger(__name__)


class MusicWorkflow(Workflow):
    """Workflow for generating background music from TTS-timed book data.

    Loads a book from the repository (which must have TTS timing data),
    generates music, and saves the book back with music audio paths
    populated in each chapter.

    This is a staged workflow — it assumes the `ai` and `tts` workflows
    have already run.
    """

    def __init__(self, repository: BookRepository) -> None:
        """Initialize with a book repository.

        Args:
            repository: Repository for loading and saving books
        """
        self._repository = repository

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Generate music for the book identified by URL.

        Args:
            url: Project Gutenberg book URL (used to derive book_id)
            start_chapter: Ignored (staged workflow processes full book)
            end_chapter: Ignored (staged workflow processes full book)
            refresh: Ignored (staged workflow uses existing data)

        Returns:
            The book with music audio paths populated

        Raises:
            Exception: If book cannot be loaded or music generation fails
        """
        logger.info("music_workflow_started", url=url)

        book_id = get_book_id_from_url(url)
        logger.info("music_workflow_book_id_derived", book_id=book_id, url=url)

        loaded = self._repository.load(book_id)
        if loaded is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )
        book = loaded
        logger.info("music_workflow_book_loaded", book_id=book_id)

        # TODO: Implement actual music generation
        logger.info("music_workflow_generation_stub", book_id=book_id)

        self._repository.save(book, book_id)
        logger.info("music_workflow_complete", book_id=book_id)

        return book
