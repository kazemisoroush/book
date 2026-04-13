"""AI-powered Project Gutenberg workflow for downloading and parsing books with section segmentation."""
import bisect
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book, BookMetadata, Section
from src.parsers.book_source import BookSource
from src.parsers.book_section_parser import BookSectionParser
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser
)
from src.config.feature_flags import FeatureFlags
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.announcement_formatter import AnnouncementFormatter
from src.parsers.prompt_builder import PromptBuilder
from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.ai.anthropic_provider import AnthropicProvider
from src.config.config import Config
from src.repository.book_repository import BookRepository
from src.repository.book_id import generate_book_id

logger = structlog.get_logger(__name__)


class AIProjectGutenbergWorkflow(Workflow):
    """Workflow for processing Project Gutenberg HTML books with AI section segmentation.

    This workflow:
    1. Gets the book and segmentation context from a BookSource
    2. Segments sections using an AI section parser
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
        reparse: bool = False,
        feature_flags: Optional[FeatureFlags] = None,
    ) -> Book:
        """Run the workflow to download, parse, and AI-segment a book.

        Args:
            url: Project Gutenberg book URL
            start_chapter: 1-based chapter index to begin parsing (default: 1).
            end_chapter: 1-based chapter index to end parsing (inclusive).
            reparse: When True, bypass the cache and run the full AI parse pipeline.

        Returns:
            A Book with sections segmented by AI.

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        logger.info("ai_workflow_started", url=url)

        ctx = self.book_source.get_book_for_segmentation(
            url, start_chapter, end_chapter, reparse,
        )
        book = ctx.book
        registry = book.character_registry
        scene_registry = book.scene_registry

        book_id = generate_book_id(book.metadata)

        # If the parser is an AISectionParser, create a new one with book-specific
        # context. Otherwise, use the provided parser as-is (for testing).
        section_parser: BookSectionParser
        if isinstance(self.section_parser, AISectionParser):
            prompt_builder = PromptBuilder(
                book_title=book.metadata.title,
                book_author=book.metadata.author,
                feature_flags=feature_flags,
            )
            section_parser = AISectionParser(
                self.section_parser.ai_provider,
                prompt_builder=prompt_builder
            )
        else:
            section_parser = self.section_parser

        logger.info(
            "ai_segmentation_started",
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
                "chapter_segmentation_started",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                section_count=len(chapter.sections),
            )
            for idx, section in enumerate(chapter.sections):
                if section.segments is not None:
                    continue  # Synthetic section — already resolved
                preceding = chapter.sections[:idx]
                section.segments, registry = section_parser.parse(
                    section, registry, context_window=preceding,
                    scene_registry=scene_registry,
                )

            bisect.insort(book.content.chapters, chapter, key=lambda c: c.number)
            book.character_registry = registry
            book.scene_registry = scene_registry
            if self._repository:
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
        formatter: Optional[AnnouncementFormatter] = None,
    ) -> None:
        """Prepend synthetic book-title / chapter-announcement sections.

        Mutates ``chapter.sections`` in-place by inserting a synthetic section
        at index 0 with ``section_type`` set and ``segments=None``.  The AI
        parser short-circuits on ``section_type`` to create segments
        deterministically (no LLM call).  Subsequent sections see it in their
        context window naturally.

        When *formatter* is provided, the text is passed through an LLM to
        produce clean, natural spoken form (e.g. fixing inverted author names).
        Otherwise falls back to raw metadata strings.
        """
        for i, chapter in enumerate(chapters):
            # Every chapter gets a chapter announcement
            if formatter:
                ann_text = formatter.format_chapter_announcement(
                    chapter.number, chapter.title,
                )
            else:
                ann_text = f"Chapter {chapter.number}. {chapter.title}." if chapter.title else f"Chapter {chapter.number}."
            chapter.sections.insert(0, Section(text=ann_text, section_type="chapter_announcement"))

            # First chapter also gets a book title announcement before the chapter announcement
            if i == 0:
                if formatter:
                    title_text = formatter.format_book_title(
                        metadata.title or "Untitled", metadata.author,
                    )
                else:
                    title = metadata.title or "Untitled"
                    author_part = f", by {metadata.author}" if metadata.author else ""
                    title_text = f"{title}{author_part}."
                chapter.sections.insert(0, Section(text=title_text, section_type="book_title"))
