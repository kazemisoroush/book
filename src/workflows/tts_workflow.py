"""TTS synthesis workflow: load book, assign voices, synthesise speech audio."""
from pathlib import Path
from typing import Optional

import structlog

from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner
from src.config import get_config
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.workflows.workflow import Workflow

logger = structlog.get_logger(__name__)


class TTSWorkflow(Workflow):
    """Staged TTS workflow: load book, assign voices, synthesise per segment.

    The provider owns all audio details: directory creation, synthesis,
    duration measurement, and setting ``segment.audio_path``.  The workflow
    iterates segments, calls the provider, and stores the returned duration.
    """

    def __init__(
        self,
        repository: BookRepository,
        tts_provider: TTSProvider,
        voice_assigner: VoiceAssigner,
        books_dir: Path = Path("books"),
    ) -> None:
        self._repository = repository
        self._tts_provider = tts_provider
        self._voice_assigner = voice_assigner
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "TTSWorkflow":
        """Factory that wires all production dependencies."""
        config = get_config()

        tts_provider = FishAudioTTSProvider(
            api_key=config.require_fish_audio_api_key(),
            books_dir=books_dir,
        )
        repository = FileBookRepository(base_dir=str(books_dir))
        voice_assigner = VoiceAssigner(tts_provider)

        return cls(
            repository=repository,
            tts_provider=tts_provider,
            voice_assigner=voice_assigner,
            books_dir=books_dir,
        )

    def run(
        self,
        book_id: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Load book from repository and synthesise speech audio for each segment.

        Args:
            book_id: Repository book identifier.
            start_chapter: Ignored (staged workflow processes full book).
            end_chapter: Ignored (staged workflow processes full book).
            refresh: Ignored (staged workflow uses existing data).

        Returns:
            The book with audio metadata populated.
        """
        logger.info("tts_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' workflow first."
            )
        logger.info("tts_workflow_loaded", book_id=book_id)

        voice_assignment = self._voice_assigner.assign(book.character_registry)
        logger.info(
            "tts_workflow_voices_assigned",
            character_count=len(voice_assignment),
        )

        for chapter in book.content.chapters:
            for section in chapter.sections:
                if section.segments is None:
                    continue
                for segment in section.segments:
                    if not segment.is_narratable:
                        continue
                    voice_id = voice_assignment.get(
                        segment.character_id or "narrator",
                        voice_assignment["narrator"],
                    )
                    duration = self._tts_provider.provide(segment, voice_id, book_id)
                    segment.duration_seconds = duration

        self._repository.save(book, book_id)
        logger.info("tts_workflow_complete", book_id=book_id)

        return book
