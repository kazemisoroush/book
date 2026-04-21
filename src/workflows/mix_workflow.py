"""Audio mixing workflow for staged pipeline."""
from pathlib import Path
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url

logger = structlog.get_logger(__name__)


class MixWorkflow(Workflow):
    """Workflow for mixing all audio layers into final chapter MP3s.

    Loads a book from the repository (which must have TTS, ambient, SFX,
    and music audio paths populated), mixes all layers into final chapter.mp3
    files, and saves the book back.

    This is a staged workflow — it assumes the `ai`, `tts`, `ambient`,
    `sfx`, and `music` workflows have already run.
    """

    def __init__(
        self,
        repository: BookRepository,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialize with a book repository.

        Args:
            repository: Repository for loading and saving books
            books_dir: Base directory for book output
        """
        self._repository = repository
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "MixWorkflow":
        """Factory that wires production dependencies.

        Args:
            books_dir: Base directory for book output (default: books/)

        Returns:
            A fully-wired MixWorkflow
        """
        from src.repository.file_book_repository import FileBookRepository

        repository = FileBookRepository(base_dir=str(books_dir))

        return cls(
            repository=repository,
            books_dir=books_dir,
        )

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Mix all audio layers for the book identified by URL.

        Args:
            url: Project Gutenberg book URL (used to derive book_id)
            start_chapter: Ignored (staged workflow processes full book)
            end_chapter: Ignored (staged workflow processes full book)
            refresh: Ignored (staged workflow uses existing data)

        Returns:
            The book after mixing

        Raises:
            Exception: If book cannot be loaded or mixing fails
        """
        logger.info("mix_workflow_started", url=url)

        book_id = get_book_id_from_url(url)
        logger.info("mix_workflow_book_id_derived", book_id=book_id, url=url)

        loaded = self._repository.load(book_id)
        if loaded is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai', 'tts', 'ambient', 'sfx', and 'music' workflows first."
            )
        book = loaded
        logger.info("mix_workflow_book_loaded", book_id=book_id)

        # Mix audio layers for each chapter
        # NOTE: This is a simplified implementation that logs the mixing intent.
        # Full ffmpeg mixing logic with build_ambient_filter_complex() and
        # OPACITY_BY_SEGMENT_TYPE would be added in a future iteration.
        audio_dir = self._books_dir / book_id / "audio"

        for chapter in book.content.chapters:
            # Check for TTS chapter.mp3
            chapter_audio_dir = audio_dir / f"chapter_{chapter.number:02d}"
            tts_path = chapter_audio_dir / "chapter.mp3"

            if not tts_path.exists():
                logger.warning(
                    "mix_workflow_tts_missing",
                    chapter_number=chapter.number,
                    expected_path=str(tts_path),
                )
                continue

            logger.info(
                "mix_workflow_mixing_chapter",
                chapter_number=chapter.number,
                tts_path=str(tts_path),
                ambient_count=len(chapter.ambient_audio_paths),
                sfx_count=len(chapter.sfx_audio_paths),
                music_count=len(chapter.music_audio_paths),
            )

            # TODO: Actual mixing logic
            # 1. Load TTS chapter.mp3
            # 2. Load ambient, SFX, music paths from chapter
            # 3. Use build_ambient_filter_complex() or similar ffmpeg logic
            # 4. Apply opacity from OPACITY_BY_SEGMENT_TYPE
            # 5. Write final mixed chapter.mp3
            #
            # For now, we just log the intent. The mixed output will be
            # the existing TTS chapter.mp3 unchanged.

        self._repository.save(book, book_id)
        logger.info("mix_workflow_complete", book_id=book_id)

        return book
