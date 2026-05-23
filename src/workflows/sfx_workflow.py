"""Sound effects generation workflow for staged pipeline."""
from pathlib import Path

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.beat import BeatType
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class SfxWorkflow(Workflow):
    """Workflow for generating sound effects per beat.

    The provider owns all audio details: directory creation, generation,
    duration measurement, and setting ``beat.audio_path``.
    """

    def __init__(
        self,
        repository: BookRepository,
        provider: SoundEffectProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._books_dir = books_dir

    def run(self, request: WorkflowRequest) -> Book:
        """Generate sound effects for the book.

        Returns:
            The book with SFX audio paths populated.
        """
        book_id = get_book_id_from_url(request.url)
        logger.info("sfx_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )
        logger.info("sfx_workflow_book_loaded", book_id=book_id)

        for chapter in book.content.chapters:
            for section in chapter.sections:
                if section.beats is None:
                    continue
                for beat in section.beats:
                    if beat.beat_type not in {BeatType.SOUND_EFFECT, BeatType.VOCAL_EFFECT}:
                        continue
                    duration = self._provider.provide(beat, book_id)
                    beat.duration_seconds = duration

        self._repository.save(book, book_id)
        logger.info("sfx_workflow_complete", book_id=book_id)

        return book
