"""AI workflow for downloading and parsing books with section beatation."""
import bisect
from typing import Optional

import structlog

from src.domain.beat import Beat, BeatType
from src.domain.models import Book, BookMetadata, Section, SectionRef
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.announcement_formatter import AnnouncementFormatter
from src.parsers.book_source import BookSource
from src.repository.book_id import generate_book_id
from src.repository.book_repository import BookRepository
from src.workflows.mood_tracker import MoodTracker
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
        registry = book.character_registry
        scene_registry = book.scene_registry
        mood_registry = book.mood_registry
        mood_tracker = MoodTracker(mood_registry)

        book_id = generate_book_id(book.metadata)

        logger.info(
            "ai_beatation_started",
            title=book.metadata.title,
            total_chapters=len(ctx.content.chapters),
            chapters_to_parse=len(ctx.chapters_to_parse),
        )

        if request.feature_flags.chapter_announcer_enabled:
            self._inject_synthetic_sections(
                ctx.chapters_to_parse, book.metadata, self._announcement_formatter,
            )

        for chapter in ctx.chapters_to_parse:
            logger.info(
                "chapter_beatation_started",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                section_count=len(chapter.sections),
            )
            last_position: Optional[SectionRef] = None
            for idx, section in enumerate(chapter.sections):
                position = SectionRef(
                    chapter=chapter.number, section=idx + 1,
                )
                last_position = position
                if section.beats is not None:
                    continue  # Synthetic section, already resolved.
                preceding = chapter.sections[:idx]
                section.beats, registry = self._section_parser.parse(
                    section, registry, context_window=preceding,
                    book_title=book.metadata.title,
                    book_author=book.metadata.author,
                    scene_registry=scene_registry,
                    mood_registry=mood_registry,
                    current_open_mood_id=mood_tracker.open_mood_id,
                )
                mood_tracker.apply(
                    self._section_parser.last_detected_mood_action, position,
                )

            if last_position is not None:
                mood_tracker.close_chapter(last_position)

            bisect.insort(book.content.chapters, chapter, key=lambda c: c.number)
            book.character_registry = registry
            self._repository.save(book, book_id)
            logger.info(
                "chapter_parsed_and_flushed",
                book_id=book_id,
                chapter_number=chapter.number,
                total_chapters_in_book=len(book.content.chapters),
            )

        mood_tracker.finalize(book)
        # Persist back-filled Section.mood_ids when moods were discovered;
        # in-loop saves happen before finalize, so the stamped ids would be
        # lost otherwise.
        if mood_registry.all():
            self._repository.save(book, book_id)

        logger.info(
            "ai_workflow_complete",
            title=book.metadata.title,
            character_count=len(registry.characters),
            mood_count=len(mood_registry.all()),
        )

        return book

    @staticmethod
    def _inject_synthetic_sections(
        chapters: list,
        metadata: BookMetadata,
        formatter: AnnouncementFormatter,
    ) -> None:
        """Prepend synthetic book-title / chapter-announcement sections.

        Mutates ``chapter.sections`` in-place by inserting a synthetic section
        at index 0 with ``section_type`` set and ``beats`` pre-resolved.
        The section text is the raw metadata; the beat text is the
        LLM-formatted spoken form.

        Because ``beats`` is already populated, the workflow loop skips
        these sections (no parser call).  Subsequent sections see them in
        their context window naturally.
        """
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
                    character_id="narrator",
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
                        character_id="narrator",
                    )],
                ))
