"""Stamps voice_id onto each narratable beat and hands chapters to the TTS provider."""
from pathlib import Path

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.characters.character_provider import CharacterProvider
from src.domain.models import Book, Chapter
from src.stores.book_store import BookStore
from src.stores.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class TTSWorkflow(Workflow):
    """Synthesises every narratable beat using voices from the character provider."""

    def __init__(
        self,
        stores: list[BookStore],
        tts_provider: TTSProvider,
        character_provider: CharacterProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._stores = stores
        self._tts_provider = tts_provider
        self._character_provider = character_provider
        self._books_dir = books_dir

    def run(self, request: WorkflowRequest) -> Book:
        """Drive the TTS provider chapter-by-chapter."""
        book_id = get_book_id_from_url(request.url)
        logger.info("tts_workflow_started", book_id=book_id)

        book = self._stores[0].load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in store for book_id={book_id!r}. "
                "Run the 'ai' workflow first."
            )
        logger.info("tts_workflow_loaded", book_id=book_id)

        voice_map = book.voice_assignments
        if not voice_map:
            raise ValueError(
                f"No voices registered for book_id={book_id!r}. "
                "Run the 'characters' workflow first."
            )
        logger.info("tts_workflow_voices_loaded", character_count=len(voice_map))

        for chapter in book.content.chapters:
            if chapter.number < request.start_chapter:
                continue
            if (
                request.end_chapter is not None
                and chapter.number > request.end_chapter
            ):
                continue
            self._stamp_voice_ids(chapter, voice_map)
            self._tts_provider.provide_collection(chapter, book_id)

        for store in self._stores:
            store.save(book)
        logger.info("tts_workflow_complete", book_id=book_id)

        return book

    @staticmethod
    def _stamp_voice_ids(chapter: Chapter, voice_map: dict[int, str]) -> None:
        """Resolve the voice for every narratable beat ahead of provider hand-off."""
        for beat in chapter.beats:
            if not beat.is_narratable:
                continue
            if beat.character_id is None:
                logger.debug(
                    "tts_workflow_beat_skipped_no_character_id",
                    beat_type=beat.beat_type.value,
                    text_preview=beat.text[:60],
                )
                continue
            voice_id = voice_map.get(beat.character_id)
            if voice_id is None:
                logger.warning(
                    "tts_workflow_missing_voice",
                    character_id=beat.character_id,
                )
                continue
            beat.voice_id = voice_id
