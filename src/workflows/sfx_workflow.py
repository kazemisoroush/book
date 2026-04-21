"""Sound effects generation workflow for staged pipeline."""
from pathlib import Path
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book, SegmentType
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.sound_effect.stable_audio_sound_effect_provider import StableAudioSoundEffectProvider
from src.config import get_config

logger = structlog.get_logger(__name__)


class SfxWorkflow(Workflow):
    """Workflow for generating sound effects from TTS-timed book data.

    Loads a book from the repository (which must have TTS timing data),
    generates sound effects, and saves the book back with SFX audio paths
    populated in each chapter.

    This is a staged workflow — it assumes the `ai` and `tts` workflows
    have already run.
    """

    def __init__(
        self,
        repository: BookRepository,
        provider: SoundEffectProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialize with a book repository and sound effect provider.

        Args:
            repository: Repository for loading and saving books
            provider: Sound effect provider for generation
            books_dir: Base directory for book output
        """
        self._repository = repository
        self._provider = provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "SfxWorkflow":
        """Factory that wires production dependencies.

        Requires:
        - STABILITY_API_KEY environment variable for sound effects

        Args:
            books_dir: Base directory for book output (default: books/)

        Returns:
            A fully-wired SfxWorkflow
        """
        from src.repository.file_book_repository import FileBookRepository

        config = get_config()

        # Instantiate Stable Audio sound effect provider
        if not config.stability_api_key:
            raise ValueError("STABILITY_API_KEY not set — required for sfx workflow")
        cache_dir = books_dir / "cache" / "sfx"
        provider = StableAudioSoundEffectProvider(
            api_key=config.stability_api_key,
            cache_dir=cache_dir,
        )

        repository = FileBookRepository(base_dir=str(books_dir))

        return cls(
            repository=repository,
            provider=provider,
            books_dir=books_dir,
        )

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Generate sound effects for the book identified by URL.

        Args:
            url: Project Gutenberg book URL (used to derive book_id)
            start_chapter: Ignored (staged workflow processes full book)
            end_chapter: Ignored (staged workflow processes full book)
            refresh: Ignored (staged workflow uses existing data)

        Returns:
            The book with SFX audio paths populated

        Raises:
            Exception: If book cannot be loaded or SFX generation fails
        """
        logger.info("sfx_workflow_started", url=url)

        book_id = get_book_id_from_url(url)
        logger.info("sfx_workflow_book_id_derived", book_id=book_id, url=url)

        loaded = self._repository.load(book_id)
        if loaded is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )
        book = loaded
        logger.info("sfx_workflow_book_loaded", book_id=book_id)

        # Generate sound effects
        sfx_dir = self._books_dir / book_id / "audio" / "sfx"

        segment_counter = 0
        for chapter in book.content.chapters:
            for section in chapter.sections:
                if section.segments is None:
                    continue
                for segment in section.segments:
                    if segment.segment_type not in {SegmentType.SOUND_EFFECT, SegmentType.VOCAL_EFFECT}:
                        continue
                    description = segment.sound_effect_detail or segment.text
                    output_path = sfx_dir / f"seg_{segment_counter:04d}.mp3"
                    segment_counter += 1

                    logger.info(
                        "sfx_workflow_generating",
                        description=description,
                        segment_type=segment.segment_type.value,
                    )

                    sfx_path = self._provider.generate(
                        description,
                        output_path,
                        duration_seconds=2.0,
                    )

                    if sfx_path is not None:
                        segment.audio_path = str(sfx_path)
                        logger.info(
                            "sfx_workflow_generated",
                            path=str(sfx_path),
                            description=description,
                        )

        self._repository.save(book, book_id)
        logger.info("sfx_workflow_complete", book_id=book_id)

        return book
