"""Sound effects generation workflow for staged pipeline."""
from pathlib import Path
from typing import Optional

import structlog

from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.config import get_config
from src.domain.models import Book, BeatType
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.workflows.workflow import Workflow

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

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "SfxWorkflow":
        """Factory that wires production dependencies."""
        config = get_config()

        provider = ElevenLabsSoundEffectProvider(
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
        """Generate sound effects for the book.

        Args:
            book_id: Repository book identifier.
            start_chapter: Ignored.
            end_chapter: Ignored.
            refresh: Ignored.

        Returns:
            The book with SFX audio paths populated.
        """
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
