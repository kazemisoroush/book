"""AI-powered Project Gutenberg workflow for downloading and parsing books with section segmentation."""
import os
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book, CharacterRegistry
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

logger = structlog.get_logger(__name__)


class AIProjectGutenbergWorkflow(Workflow):
    """Workflow for processing Project Gutenberg HTML books with AI section segmentation.

    This workflow orchestrates:
    1. Downloading the book zip file
    2. Finding the HTML file
    3. Parsing metadata
    4. Parsing content
    5. Segmenting sections using an AI section parser
    6. Assembling the Book object

    This class is completely standalone — it does not inherit from or delegate
    to ProjectGutenbergWorkflow. It uses AISectionParser to identify dialogue
    vs narration for each section in each chapter (up to chapter_limit chapters
    if set).

    Follows SOLID principles:
    - Single Responsibility: Orchestrates AI-powered book processing pipeline
    - Dependency Inversion: Depends on parser/downloader abstractions
    """

    def __init__(
        self,
        downloader,
        metadata_parser,
        content_parser,
        section_parser,
        chapter_limit: Optional[int] = None,
    ):
        """Initialize the workflow with dependencies.

        Args:
            downloader: BookDownloader instance
            metadata_parser: BookMetadataParser instance
            content_parser: BookContentParser instance
            section_parser: BookSectionParser instance for AI segmentation
            chapter_limit: If set, only the first N chapters will be segmented
        """
        self.downloader = downloader
        self.metadata_parser = metadata_parser
        self.content_parser = content_parser
        self.section_parser = section_parser
        self.chapter_limit = chapter_limit

    @classmethod
    def create(cls, chapter_limit: Optional[int] = None) -> "AIProjectGutenbergWorkflow":
        """Factory method to create workflow with default dependencies.

        Wires:
        - ProjectGutenbergHTMLBookDownloader
        - StaticProjectGutenbergHTMLMetadataParser
        - StaticProjectGutenbergHTMLContentParser
        - AISectionParser backed by AWSBedrockProvider using Config.from_env()

        Args:
            chapter_limit: If set, only the first N chapters will be segmented

        Returns:
            AIProjectGutenbergWorkflow instance with wired dependencies
        """
        downloader = ProjectGutenbergHTMLBookDownloader()
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        content_parser = StaticProjectGutenbergHTMLContentParser()

        config = Config.from_env()
        ai_provider = AWSBedrockProvider(config)
        section_parser = AISectionParser(ai_provider)

        return cls(
            downloader,
            metadata_parser,
            content_parser,
            section_parser,
            chapter_limit=chapter_limit,
        )

    def run(self, input: str) -> Book:
        """Run the workflow to download, parse, and AI-segment a book.

        For each chapter (up to chapter_limit if set), every section is passed
        through the AI section parser.  A CharacterRegistry is bootstrapped
        with the default narrator and threaded through all section parses so
        that character IDs remain consistent across the full book.

        Args:
            input: Project Gutenberg book URL (e.g.,
                   https://www.gutenberg.org/files/123/123-h.zip)

        Returns:
            A Book with sections segmented by AI and ``character_registry``
            populated with all characters discovered during parsing
            (narrator always present).

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        # Step 1: Download the book
        logger.info("ai_workflow_started", url=input)
        if not self.downloader.parse(input):
            raise RuntimeError(f"Failed to download book from {input}")

        # Step 2: Find the downloaded HTML file
        book_id = self.downloader._extract_book_id(input)
        download_dir = f"books/{book_id}"

        html_file = self._find_html_file(download_dir)
        if not html_file:
            raise RuntimeError(f"No HTML file found in {download_dir}")

        logger.info("parsing_started", html_file=html_file)

        # Step 3: Read HTML content
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Step 4: Parse metadata and content
        metadata = self.metadata_parser.parse(html_content)
        content = self.content_parser.parse(html_content)

        logger.info(
            "ai_segmentation_started",
            title=metadata.title,
            total_chapters=len(content.chapters),
            chapter_limit=self.chapter_limit,
        )

        # Step 5: Segment sections using the AI section parser, threading
        # the CharacterRegistry through every call so character IDs are
        # consistent across the entire book.
        registry = CharacterRegistry.with_default_narrator()

        chapters_to_segment = content.chapters
        if self.chapter_limit is not None:
            chapters_to_segment = content.chapters[:self.chapter_limit]

        _CONTEXT_WINDOW_SIZE = 3

        for chapter in chapters_to_segment:
            logger.info(
                "chapter_segmentation_started",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                section_count=len(chapter.sections),
            )
            for idx, section in enumerate(chapter.sections):
                # Build the context window: up to _CONTEXT_WINDOW_SIZE
                # preceding sections within the same chapter.
                # Context never crosses chapter boundaries.
                start = max(0, idx - _CONTEXT_WINDOW_SIZE)
                context_window = chapter.sections[start:idx]
                section.segments, registry = self.section_parser.parse(
                    section, registry, context_window=context_window
                )

        logger.info(
            "ai_workflow_complete",
            title=metadata.title,
            character_count=len(registry.characters),
        )

        # Step 6: Assemble and return Book with character_registry attached
        return Book(metadata=metadata, content=content, character_registry=registry)

    def _find_html_file(self, directory: str) -> Optional[str]:
        """Find the first HTML file in the directory recursively.

        Args:
            directory: Directory to search

        Returns:
            Path to HTML file, or None if not found
        """
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.html', '.htm')):
                    return os.path.join(root, filename)
        return None
