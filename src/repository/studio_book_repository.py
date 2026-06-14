"""BookRepository backed by ElevenLabs Studio.

Each call to :meth:`StudioBookRepository.save_chapter` upserts a Studio
project named after the book and a chapter named ``Chapter {N}``, then
replaces the chapter's content with one ``tts_node`` per narratable beat.
Voice per node comes from :attr:`Book.voice_assignments`; a constructor-
supplied ``default_voice_id`` fills in the gaps so the AI workflow can
push to Studio before the characters workflow runs.

The repository is write-only on the Studio side. ``save``, ``save_input``,
``load``, ``load_input``, and ``exists`` are no-ops; pair this repo with a
:class:`FileBookRepository` to keep cache-resume working.
"""
from typing import Any, Optional

import structlog

from src.domain.beat import Beat
from src.domain.models import Book, Chapter
from src.repository.book_repository import BookRepository

logger = structlog.get_logger(__name__)


class StudioBookRepository(BookRepository):
    """Mirror parsed chapters into an ElevenLabs Studio project."""

    def __init__(self, client: Any, default_voice_id: str) -> None:
        self._client = client
        self._default_voice_id = default_voice_id
        self._project_id_cache: dict[str, str] = {}
        self._chapter_id_cache: dict[tuple[str, int], str] = {}

    def save(self, book: Book) -> None:
        """No-op; Studio is updated per chapter, not per book."""
        del book

    def save_chapter(self, book: Book, chapter: Chapter) -> None:
        """Push *chapter* into the Studio project for *book*, replacing its blocks."""
        blocks = self._build_blocks(book, chapter)
        if not blocks:
            logger.info(
                "studio_save_chapter_skipped_no_narratable_beats",
                book_id=book.book_id,
                chapter_number=chapter.number,
            )
            return

        project_id = self._ensure_project(book)
        chapter_id = self._ensure_chapter(project_id, chapter)
        self._client.studio.projects.chapters.update(
            project_id,
            chapter_id,
            content={"blocks": blocks},
        )
        logger.info(
            "studio_chapter_updated",
            book_id=book.book_id,
            chapter_number=chapter.number,
            project_id=project_id,
            chapter_id=chapter_id,
            block_count=len(blocks),
        )

    def save_input(self, book: Book) -> None:
        """No-op; the input snapshot is held by the local file repo."""
        del book

    def load(self, book_id: str) -> Optional[Book]:
        """Studio is write-only here; always returns ``None``."""
        del book_id
        return None

    def load_input(self, book_id: str) -> Optional[Book]:
        """Studio is write-only here; always returns ``None``."""
        del book_id
        return None

    def exists(self, book_id: str) -> bool:
        """Studio is write-only here; always returns ``False`` to never block resume."""
        del book_id
        return False

    def _ensure_project(self, book: Book) -> str:
        cached = self._project_id_cache.get(book.book_id)
        if cached is not None:
            return cached

        existing = self._find_project_id(book.book_id)
        if existing is not None:
            self._project_id_cache[book.book_id] = existing
            logger.info(
                "studio_project_reused",
                book_id=book.book_id,
                project_id=existing,
            )
            return existing

        created = self._client.studio.projects.create(
            name=book.book_id,
            default_paragraph_voice_id=self._default_voice_id,
            title=book.metadata.title,
            author=book.metadata.author or None,
            source_type="book",
        )
        project_id = str(created.project.project_id)
        self._project_id_cache[book.book_id] = project_id
        logger.info(
            "studio_project_created",
            book_id=book.book_id,
            project_id=project_id,
        )
        return project_id

    def _find_project_id(self, book_id: str) -> Optional[str]:
        response = self._client.studio.projects.list()
        for project in response.projects:
            if project.name == book_id:
                return str(project.project_id)
        return None

    def _ensure_chapter(self, project_id: str, chapter: Chapter) -> str:
        key = (project_id, chapter.number)
        cached = self._chapter_id_cache.get(key)
        if cached is not None:
            return cached

        chapter_name = chapter.display_name
        existing = self._find_chapter_id(project_id, chapter_name)
        if existing is not None:
            self._chapter_id_cache[key] = existing
            logger.info(
                "studio_chapter_reused",
                project_id=project_id,
                chapter_number=chapter.number,
                chapter_id=existing,
            )
            return existing

        created = self._client.studio.projects.chapters.create(
            project_id,
            name=chapter_name,
        )
        chapter_id = str(created.chapter.chapter_id)
        self._chapter_id_cache[key] = chapter_id
        logger.info(
            "studio_chapter_created",
            project_id=project_id,
            chapter_number=chapter.number,
            chapter_id=chapter_id,
        )
        return chapter_id

    def _find_chapter_id(self, project_id: str, chapter_name: str) -> Optional[str]:
        response = self._client.studio.projects.chapters.list(project_id)
        for chapter in response.chapters:
            if chapter.name == chapter_name:
                return str(chapter.chapter_id)
        return None

    def _build_blocks(self, book: Book, chapter: Chapter) -> list[dict]:
        blocks: list[dict] = []
        for beat in chapter.beats:
            node = self._beat_to_node(book, beat)
            if node is None:
                continue
            blocks.append({"sub_type": "p", "nodes": [node]})
        return blocks

    def _beat_to_node(self, book: Book, beat: Beat) -> Optional[dict]:
        text = beat.text.strip()
        if not text or not beat.is_narratable:
            return None
        voice_id = book.voice_assignments.get(
            beat.character_id, self._default_voice_id,
        ) if beat.character_id is not None else self._default_voice_id
        return {"type": "tts_node", "text": text, "voice_id": voice_id}
