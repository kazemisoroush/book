"""Ambient audio generation workflow for staged pipeline."""
from pathlib import Path

import structlog

from src.audio.ambient.ambient_provider import AmbientProvider
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class AmbientWorkflow(Workflow):
    """Workflow for generating ambient audio per scene.

    The provider owns all audio details: directory creation, generation,
    duration measurement, and path storage.
    """

    def __init__(
        self,
        repository: BookRepository,
        provider: AmbientProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._books_dir = books_dir

    def run(self, request: WorkflowRequest) -> Book:
        """Generate ambient audio for scenes in the book.

        Returns:
            The book with ambient audio generated for scenes.
        """
        book_id = get_book_id_from_url(request.url)
        logger.info("ambient_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )
        logger.info("ambient_workflow_book_loaded", book_id=book_id)

        for scene in book.scene_registry.all():
            if scene.ambient_prompt is None:
                continue
            self._provider.provide(scene, book_id)

        self._repository.save(book, book_id)
        logger.info("ambient_workflow_complete", book_id=book_id)

        return book
