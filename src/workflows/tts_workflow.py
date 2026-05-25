"""TTS synthesis workflow: load book, look up voices, synthesise speech audio."""
from pathlib import Path

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.characters.character_provider import CharacterProvider
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class TTSWorkflow(Workflow):
    """Load a parsed book, resolve voices via the character provider, synthesise per beat.

    The provider owns all audio details. The workflow iterates beats and
    hands each one its voice token.
    """

    def __init__(
        self,
        repository: BookRepository,
        tts_provider: TTSProvider,
        character_provider: CharacterProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._repository = repository
        self._tts_provider = tts_provider
        self._character_provider = character_provider
        self._books_dir = books_dir

    def run(self, request: WorkflowRequest) -> Book:
        """Load book from repository and synthesise speech audio for each beat.

        Returns:
            The book with audio metadata populated.
        """
        book_id = get_book_id_from_url(request.url)
        logger.info("tts_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' workflow first."
            )
        logger.info("tts_workflow_loaded", book_id=book_id)

        voice_map = self._character_provider.get_all(book)
        if not voice_map:
            raise ValueError(
                f"No voices registered for book_id={book_id!r}. "
                "Run the 'characters' workflow first."
            )
        logger.info("tts_workflow_voices_loaded", character_count=len(voice_map))

        for chapter in book.content.chapters:
            for section in chapter.sections:
                if section.beats is None:
                    continue
                for beat in section.beats:
                    if not beat.is_narratable:
                        continue
                    if beat.character_id is None:
                        continue
                    voice_id = voice_map.get(beat.character_id)
                    if voice_id is None:
                        logger.warning(
                            "tts_workflow_missing_voice",
                            character_id=beat.character_id,
                        )
                        continue
                    self._tts_provider.provide(beat, voice_id, book_id)

        self._repository.save(book, book_id)
        logger.info("tts_workflow_complete", book_id=book_id)

        return book
