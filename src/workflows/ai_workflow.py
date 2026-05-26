"""AI workflow for downloading and parsing books with section beatation."""
import bisect

import structlog

from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_NAME
from src.domain.character_id import build_character_id
from src.domain.models import Book, BookMetadata, Section
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.book_source import BookSource
from src.prompts.builder.announcement_formatter import AnnouncementFormatter
from src.repository.book_id import generate_book_id
from src.repository.book_repository import BookRepository
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class AIWorkflow(Workflow):
    """Workflow for AI section beatation of any book.

    This workflow:
    1. Gets the book and beatation context from a BookSource
    2. Beats sections using the injected AISectionParser
    3. Flushes chapters to the repository

    The BookSource handles all download/parse/cache/resume logic.
    """

    def __init__(
        self,
        book_source: BookSource,
        section_parser: AISectionParser,
        announcement_formatter: AnnouncementFormatter,
        repository: BookRepository,
    ) -> None:
        self.book_source = book_source
        self._section_parser = section_parser
        self._announcement_formatter = announcement_formatter
        self._repository = repository

    def run(self, request: WorkflowRequest) -> Book:
        """Run the workflow to download, parse, and AI-beat a book.

        Returns:
            A Book with sections beated by AI.

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        logger.info("ai_workflow_started", url=request.url)

        ctx = self.book_source.get_book(
            request.url, request.start_chapter, request.end_chapter, request.refresh,
        )
        book = ctx.book
        scene_registry = book.scene_registry

        book_id = generate_book_id(book.metadata)
        registry = book.character_registry

        logger.info(
            "ai_beatation_started",
            title=book.metadata.title,
            total_chapters=len(ctx.content.chapters),
            chapters_to_parse=len(ctx.chapters_to_parse),
        )

        if request.feature_flags.chapter_announcer_enabled:
            self._inject_synthetic_sections(
                ctx.chapters_to_parse, book.metadata, book_id, self._announcement_formatter,
            )

        for chapter in ctx.chapters_to_parse:
            logger.info(
                "chapter_beatation_started",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                section_count=len(chapter.sections),
            )
            for idx, section in enumerate(chapter.sections):
                if section.beats is not None:
                    continue  # Synthetic section, already resolved.
                preceding = chapter.sections[:idx]
                section.beats, registry = self._section_parser.parse(
                    section, registry, context_window=preceding,
                    book_id=book_id,
                    book_title=book.metadata.title,
                    book_author=book.metadata.author,
                    scene_registry=scene_registry,
                )

            bisect.insort(book.content.chapters, chapter, key=lambda c: c.number)
            book.character_registry = registry
            self._repository.save(book, book_id)
            logger.info(
                "chapter_parsed_and_flushed",
                book_id=book_id,
                chapter_number=chapter.number,
                total_chapters_in_book=len(book.content.chapters),
            )

        logger.info(
            "ai_workflow_complete",
            title=book.metadata.title,
            character_count=len(registry.characters),
        )

        return book

    @staticmethod
    def _inject_synthetic_sections(
        chapters: list,
        metadata: BookMetadata,
        book_id: str,
        formatter: AnnouncementFormatter,
    ) -> None:
        """Prepend synthetic book-title and chapter-announcement sections in place."""
        for i, chapter in enumerate(chapters):
            raw_ann = (
                f"Chapter {chapter.number}. {chapter.title}."
                if chapter.title
                else f"Chapter {chapter.number}."
            )
            spoken_ann = formatter.format_chapter_announcement(chapter.number, chapter.title)
            chapter.sections.insert(0, Section(
                text=raw_ann,
                section_type="chapter_announcement",
                beats=[Beat(
                    text=spoken_ann,
                    beat_type=BeatType.CHAPTER_ANNOUNCEMENT,
                    character_id=build_character_id(book_id, NARRATOR_NAME),
                )],
            ))

            if i == 0:
                title = metadata.title or "Untitled"
                author_part = f", by {metadata.author}" if metadata.author else ""
                raw_title = f"{title}{author_part}."
                spoken_title = formatter.format_book_title(title, metadata.author)
                chapter.sections.insert(0, Section(
                    text=raw_title,
                    section_type="book_title",
                    beats=[Beat(
                        text=spoken_title,
                        beat_type=BeatType.BOOK_TITLE,
                        character_id=build_character_id(book_id, NARRATOR_NAME),
                    )],
                ))
