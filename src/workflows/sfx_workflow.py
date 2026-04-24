"""Sound effects generation workflow for staged pipeline."""
from pathlib import Path
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book, SegmentType
from src.repository.book_repository import BookRepository
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider

logger = structlog.get_logger(__name__)


class SfxWorkflow(Workflow):
    """Workflow for generating sound effects per segment.

    The provider owns all audio details: directory creation, generation,
    duration measurement, and setting ``segment.audio_path``.
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
        from src.repository.file_book_repository import FileBookRepository
        from src.audio.sound_effect.stable_audio_sound_effect_provider import StableAudioSoundEffectProvider
        from src.config import get_config

        config = get_config()

        if not config.stability_api_key:
            raise ValueError("STABILITY_API_KEY not set — required for sfx workflow")
        provider = StableAudioSoundEffectProvider(
            api_key=config.stability_api_key,
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
                if section.segments is None:
                    continue
                for segment in section.segments:
                    if segment.segment_type not in {SegmentType.SOUND_EFFECT, SegmentType.VOCAL_EFFECT}:
                        continue
                    duration = self._provider.provide(segment, book_id)
                    segment.duration_seconds = duration

        self._repository.save(book, book_id)
        logger.info("sfx_workflow_complete", book_id=book_id)

        return book
