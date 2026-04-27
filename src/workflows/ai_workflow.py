"""AI-powered Project Gutenberg workflow for downloading and parsing books with section beatation."""
import bisect
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config.config import Config
from src.config.feature_flags import FeatureFlags
from src.domain.models import Beat, BeatType, Book, BookMetadata, Section, SectionRef
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader,
)
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.announcement_formatter import AnnouncementFormatter
from src.parsers.book_section_parser import BookSectionParser
from src.parsers.book_source import BookSource
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
from src.parsers.prompt_builder import PromptBuilder
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.repository.book_id import generate_book_id
from src.repository.book_repository import BookRepository
from src.workflows.mood_tracker import MoodTracker
from src.workflows.workflow import Workflow

logger = structlog.get_logger(__name__)


class AIProjectGutenbergWorkflow(Workflow):
    """Workflow for processing Project Gutenberg HTML books with AI section beatation.

    This workflow:
    1. Gets the book and beatation context from a BookSource
    2. Beats sections using an AI section parser
    3. Flushes chapters to the repository

    The BookSource handles all download/parse/cache/resume logic.
    """

    def __init__(
        self,
        book_source: BookSource,
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> None:
        self.book_source = book_source
        self.section_parser = section_parser
        self._repository = repository

    @classmethod
    def create(
        cls,
        repository: Optional[BookRepository] = None,
    ) -> "AIProjectGutenbergWorkflow":
        """Factory method to create workflow with default dependencies."""
        downloader = ProjectGutenbergHTMLBookDownloader()
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        content_parser = StaticProjectGutenbergHTMLContentParser()
        book_source = ProjectGutenbergBookSource(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            repository=repository,
        )

        config = Config.from_env()
        ai_provider: AIProvider
        if config.ai_provider == "anthropic":
            from src.ai.anthropic_provider import AnthropicProvider
            ai_provider = AnthropicProvider(config)
        else:
            ai_provider = AWSBedrockProvider(config)
        section_parser = AISectionParser(ai_provider)

        return cls(
            book_source=book_source,
            section_parser=section_parser,
            repository=repository,
        )

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
        feature_flags: Optional[FeatureFlags] = None,
    ) -> Book:
        """Run the workflow to download, parse, and AI-beat a book.

        Args:
            url: Project Gutenberg book URL
            start_chapter: 1-based chapter index to begin parsing (default: 1).
            end_chapter: 1-based chapter index to end parsing (inclusive).
            refresh: When True, bypass the cache and re-run the workflow from scratch.

        Returns:
            A Book with sections beated by AI.

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        logger.info("ai_workflow_started", url=url)

        ctx = self.book_source.get_book_for_beatation(
            url, start_chapter, end_chapter, refresh,
        )
        book = ctx.book
        registry = book.character_registry
        scene_registry = book.scene_registry
        mood_registry = book.mood_registry
        mood_tracker = MoodTracker(mood_registry)

        book_id = generate_book_id(book.metadata)

        # If the parser is an AISectionParser, create a new one with book-specific
        # context. Otherwise, use the provided parser as-is (for testing).
        section_parser: BookSectionParser
        if isinstance(self.section_parser, AISectionParser):
            prompt_builder = PromptBuilder(
                book_title=book.metadata.title,
                book_author=book.metadata.author,
            )
            section_parser = AISectionParser(
                self.section_parser.ai_provider,
                prompt_builder=prompt_builder
            )
        else:
            section_parser = self.section_parser

        logger.info(
            "ai_beatation_started",
            title=book.metadata.title,
            total_chapters=len(ctx.content.chapters),
            chapters_to_parse=len(ctx.chapters_to_parse),
        )

        flags = feature_flags or FeatureFlags()
        if flags.chapter_announcer_enabled:
            # Use LLM-based formatter when a real AI parser is in use,
            # fall back to raw text for tests with fake parsers.
            formatter: Optional[AnnouncementFormatter] = None
            if isinstance(self.section_parser, AISectionParser):
                formatter = AnnouncementFormatter(self.section_parser.ai_provider)
            self._inject_synthetic_sections(
                ctx.chapters_to_parse, book.metadata, formatter,
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
                    continue  # Synthetic section — already resolved
                preceding = chapter.sections[:idx]
                section.beats, registry = section_parser.parse(
                    section, registry, context_window=preceding,
                    scene_registry=scene_registry,
                    mood_registry=mood_registry,
                    current_open_mood_id=mood_tracker.open_mood_id,
                )
                if isinstance(section_parser, AISectionParser):
                    mood_tracker.apply(
                        section_parser.last_detected_mood_action, position,
                    )

            if last_position is not None:
                mood_tracker.close_chapter(last_position)

            bisect.insort(book.content.chapters, chapter, key=lambda c: c.number)
            book.character_registry = registry
            book.scene_registry = scene_registry
            book.mood_registry = mood_registry
            if self._repository:
                self._repository.save(book, book_id)
                logger.info(
                    "chapter_parsed_and_flushed",
                    book_id=book_id,
                    chapter_number=chapter.number,
                    total_chapters_in_book=len(book.content.chapters),
                )

        mood_tracker.finalize(book)
        book.mood_registry = mood_registry
        # Persist back-filled Section.mood_ids when moods were discovered;
        # in-loop saves happen before finalize, so the stamped ids would be
        # lost otherwise. Fake parsers that never emit mood actions leave
        # the registry empty and this save is skipped.
        if self._repository and mood_registry.all():
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
        formatter: Optional[AnnouncementFormatter] = None,
    ) -> None:
        """Prepend synthetic book-title / chapter-announcement sections.

        Mutates ``chapter.sections`` in-place by inserting a synthetic section
        at index 0 with ``section_type`` set and ``beats`` pre-resolved.
        The section text is the raw metadata; the beat text is the
        LLM-formatted spoken form (when *formatter* is provided).

        Because ``beats`` is already populated, the workflow loop skips
        these sections (no parser call).  Subsequent sections see them in
        their context window naturally.
        """
        for i, chapter in enumerate(chapters):
            # Every chapter gets a chapter announcement
            raw_ann = f"Chapter {chapter.number}. {chapter.title}." if chapter.title else f"Chapter {chapter.number}."
            spoken_ann = formatter.format_chapter_announcement(chapter.number, chapter.title) if formatter else raw_ann
            chapter.sections.insert(0, Section(
                text=raw_ann,
                section_type="chapter_announcement",
                beats=[Beat(
                    text=spoken_ann,
                    beat_type=BeatType.CHAPTER_ANNOUNCEMENT,
                    character_id="narrator",
                )],
            ))

            # First chapter also gets a book title announcement before the chapter announcement
            if i == 0:
                title = metadata.title or "Untitled"
                author_part = f", by {metadata.author}" if metadata.author else ""
                raw_title = f"{title}{author_part}."
                spoken_title = formatter.format_book_title(title, metadata.author) if formatter else raw_title
                chapter.sections.insert(0, Section(
                    text=raw_title,
                    section_type="book_title",
                    beats=[Beat(
                        text=spoken_title,
                        beat_type=BeatType.BOOK_TITLE,
                        character_id="narrator",
                    )],
                ))
