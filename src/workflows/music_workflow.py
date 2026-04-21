"""Music generation workflow for staged pipeline."""
from pathlib import Path
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.audio.music.music_provider import MusicProvider
from src.audio.music.suno_music_provider import SunoMusicProvider
from src.config import get_config

logger = structlog.get_logger(__name__)


class MusicWorkflow(Workflow):
    """Workflow for generating background music from TTS-timed book data.

    Loads a book from the repository (which must have TTS timing data),
    generates music, and saves the book back with music audio paths
    populated in each chapter.

    This is a staged workflow — it assumes the `ai` and `tts` workflows
    have already run.
    """

    def __init__(
        self,
        repository: BookRepository,
        provider: MusicProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialize with a book repository and music provider.

        Args:
            repository: Repository for loading and saving books
            provider: Music provider for generation
            books_dir: Base directory for book output
        """
        self._repository = repository
        self._provider = provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "MusicWorkflow":
        """Factory that wires production dependencies.

        Requires:
        - SUNO_API_KEY environment variable for music generation

        Args:
            books_dir: Base directory for book output (default: books/)

        Returns:
            A fully-wired MusicWorkflow
        """
        from src.repository.file_book_repository import FileBookRepository

        config = get_config()

        # Instantiate Suno music provider
        if not config.suno_api_key:
            raise ValueError("SUNO_API_KEY not set — required for music workflow")
        cache_dir = books_dir / "cache" / "music"
        provider = SunoMusicProvider(
            api_key=config.suno_api_key,
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

        # Generate music for each chapter
        music_dir = self._books_dir / book_id / "audio" / "music"
        music_dir.mkdir(parents=True, exist_ok=True)

        for chapter in book.content.chapters:
            prompt = f"atmospheric background music for {chapter.title}"
            output_path = music_dir / f"ch_{chapter.number:02d}.mp3"

            logger.info(
                "music_workflow_generating",
                chapter_number=chapter.number,
                prompt=prompt,
            )

            music_path = self._provider.generate(
                prompt,
                output_path,
                duration_seconds=60.0,
            )

            if music_path is not None:
                chapter.music_audio_paths.append(str(music_path))
                logger.info(
                    "music_workflow_generated",
                    chapter_number=chapter.number,
                    path=str(music_path),
                )

        self._repository.save(book, book_id)
        logger.info("music_workflow_complete", book_id=book_id)

        return book
