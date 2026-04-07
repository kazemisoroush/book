"""AI-powered Project Gutenberg workflow for downloading and parsing books with section segmentation."""
import bisect
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book
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
from src.parsers.ai_section_parser import AISectionParser
from src.ai.aws_bedrock_provider import AWSBedrockProvider
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

        logger.info(
            "ai_segmentation_started",
            title=book.metadata.title,
            total_chapters=len(ctx.content.chapters),
            chapters_to_parse=len(ctx.chapters_to_parse),
        )

        for chapter in ctx.chapters_to_parse:
            logger.info(
                "chapter_segmentation_started",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                section_count=len(chapter.sections),
            )
            for idx, section in enumerate(chapter.sections):
                preceding = chapter.sections[:idx]
                section.segments, registry = self.section_parser.parse(
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
