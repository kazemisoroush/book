"""TTS synthesis workflow: load book, assign voices, synthesise speech audio."""
from pathlib import Path
from typing import Optional

import structlog

from src.domain.models import Book
from src.repository.book_id import generate_book_id
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner
from src.config.feature_flags import FeatureFlags
from src.audio.audio_orchestrator import AudioOrchestrator
from src.workflows.workflow import Workflow

logger = structlog.get_logger(__name__)


class TTSWorkflow(Workflow):
    """Staged TTS workflow: load book from repository, assign voices, synthesise audio.

    Assumes the ``ai`` workflow has already run and saved a parsed book to the
    repository. Loads the book, assigns voices to characters, synthesises
    speech audio for every chapter, and saves the book back with audio metadata.

    Use :meth:`create` to get an instance wired with production dependencies.
    """

    def __init__(
        self,
        repository: BookRepository,
        tts_provider: TTSProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialise with explicit dependencies.

        Args:
            repository: Book repository for loading/saving books.
            tts_provider: TTS provider for audio synthesis.
            books_dir: Base directory for book output (default: ``books/``).
        """
        self._repository = repository
        self._tts_provider = tts_provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "TTSWorkflow":
        """Factory that wires all production dependencies.

        Requires:
        - ``FISH_AUDIO_API_KEY`` environment variable for TTS

        Args:
            books_dir: Base directory for book output (default: ``books/``).

        Returns:
            A fully-wired ``TTSWorkflow``.
        """
        from src.config import get_config
        from src.repository.file_book_repository import FileBookRepository

        config = get_config()

        fish_api_key = config.fish_audio_api_key
        if not fish_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set — required for tts workflow")
        tts_provider = FishAudioTTSProvider(api_key=fish_api_key)

        repository = FileBookRepository(base_dir=str(books_dir))

        return cls(
            repository=repository,
            tts_provider=tts_provider,
            books_dir=books_dir,
        )

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: int | None = None,
        refresh: bool = False,
        debug: bool = False,
        feature_flags: Optional[FeatureFlags] = None,
    ) -> Book:
        """Load book from repository and synthesise speech audio for each chapter.

        Args:
            url: Book URL (used to derive book_id for repository lookup).
            start_chapter: Ignored (staged workflow processes full book).
            end_chapter: Ignored (staged workflow processes full book).
            refresh: Ignored (staged workflow uses existing data).
            debug: When ``True``, keep individual segment MP3 files alongside
                   the stitched ``chapter.mp3``.  Defaults to ``False``.
            feature_flags: Feature toggles for audio synthesis.

        Returns:
            The book with audio metadata populated.
        """
        logger.info("tts_workflow_started", url=url)

        flags = feature_flags or FeatureFlags()

        # Load book from repository
        book_id = get_book_id_from_url(url)
        loaded = self._repository.load(book_id)
        if loaded is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r} (url={url!r}). "
                "Run the 'ai' workflow first."
            )
        book = loaded
        logger.info("tts_workflow_loaded", book_id=book_id)

        # Compute output directory
        book_id = generate_book_id(book.metadata)
        audio_dir = self._books_dir / book_id / "audio"
        audio_orchestrator = AudioOrchestrator(
            provider=self._tts_provider,
            output_dir=audio_dir,
            debug=debug,
            feature_flags=flags,
        )

        # Assign voices
        voice_assigner = VoiceAssigner(self._tts_provider)
        voice_assignment = voice_assigner.assign(book.character_registry)

        logger.info(
            "tts_workflow_voices_assigned",
            character_count=len(voice_assignment),
        )

        # Synthesise each chapter
        for chapter in book.content.chapters:
            logger.info(
                "tts_workflow_synthesising_chapter",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
            )
            audio_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chapter.number,
                voice_assignment=voice_assignment,
            )

        # Save book back to repository
        self._repository.save(book, book_id)
        logger.info("tts_workflow_complete", book_id=book_id)

        return book
