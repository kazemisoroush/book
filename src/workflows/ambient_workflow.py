"""Ambient audio generation workflow for staged pipeline."""
from pathlib import Path
from typing import Optional

import structlog

from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.ambient.elevenlabs_ambient_provider import ElevenLabsAmbientProvider
from src.config import get_config
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.workflows.workflow import Workflow

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

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "AmbientWorkflow":
        """Factory that wires production dependencies."""
        config = get_config()

        provider = ElevenLabsAmbientProvider(
            api_key=config.elevenlabs_api_key or "",
            books_dir=books_dir,
        )
        repository = FileBookRepository(base_dir=str(books_dir))

        return cls(
            repository=repository,
            provider=provider,
            books_dir=books_dir,
        )

    def run(
        self,
        book_id: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Generate ambient audio for scenes in the book.

        Args:
            book_id: Repository book identifier.
            start_chapter: Ignored.
            end_chapter: Ignored.
            refresh: Ignored.

        Returns:
            The book with ambient audio generated for scenes.
        """
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
