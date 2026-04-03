"""AI-powered Project Gutenberg workflow for downloading and parsing books with section segmentation."""
import os
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book, CharacterRegistry, SceneRegistry
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

    This workflow orchestrates:
    1. Downloading the book zip file
    2. Finding the HTML file
    3. Parsing metadata
    4. Parsing content
    5. Segmenting sections using an AI section parser
    6. Assembling the Book object

    When a ``BookRepository`` is provided, the workflow checks for a cached
    parsed book before invoking the AI pipeline.  If the cache hits (and
    ``reparse`` is not set), the cached ``Book`` is returned immediately,
    saving AI tokens and latency.

    The ``chapter_limit`` is an invocation parameter passed to ``run()``, not
    a constructor parameter. A single workflow instance can thus be reused
    for different invocations without reconstruction.

    Follows SOLID principles:
    - Single Responsibility: Orchestrates AI-powered book processing pipeline
    - Dependency Inversion: Depends on parser/downloader abstractions
    """

    def __init__(
        self,
        downloader,  # type: ignore[no-untyped-def]
        metadata_parser,  # type: ignore[no-untyped-def]
        content_parser,  # type: ignore[no-untyped-def]
        section_parser,  # type: ignore[no-untyped-def]
        repository: Optional[BookRepository] = None,
    ):
        """Initialize the workflow with dependencies.

        Args:
            downloader: BookDownloader instance
            metadata_parser: BookMetadataParser instance
            content_parser: BookContentParser instance
            section_parser: BookSectionParser instance for AI segmentation
            repository: Optional BookRepository for caching parsed books
        """
        self.downloader = downloader
        self.metadata_parser = metadata_parser
        self.content_parser = content_parser
        self.section_parser = section_parser
        self._repository = repository

    @classmethod
    def create(
        cls,
        repository: Optional[BookRepository] = None,
    ) -> "AIProjectGutenbergWorkflow":
        """Factory method to create workflow with default dependencies.

        Wires:
        - ProjectGutenbergHTMLBookDownloader
        - StaticProjectGutenbergHTMLMetadataParser
        - StaticProjectGutenbergHTMLContentParser
        - AISectionParser backed by AWSBedrockProvider using Config.from_env()

        Args:
            repository: Optional BookRepository for caching parsed books.

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
            repository=repository,
        )

    def run(self, url: str, chapter_limit: int = 3, reparse: bool = False) -> Book:
        """Run the workflow to download, parse, and AI-segment a book.

        When a ``BookRepository`` was provided at construction time, the
        workflow first checks for a cached parsed book.  If the cache
        contains an entry for this book **and** ``reparse`` is ``False``,
        the cached ``Book`` is returned without invoking the AI pipeline.

        For each chapter (up to ``chapter_limit``), every section is passed
        through the AI section parser. A CharacterRegistry is bootstrapped
        with the default narrator and threaded through all section parses so
        that character IDs remain consistent across the entire book.

        Args:
            url: Project Gutenberg book URL (e.g.,
                 https://www.gutenberg.org/files/123/123-h.zip)
            chapter_limit: Maximum number of chapters to segment and include in
                           the returned ``Book``. ``0`` means all chapters.
                           Defaults to 3.
            reparse: When ``True``, bypass the cache and run the full AI
                     parse pipeline.  The result is still saved to the
                     repository (overwriting any existing cached book).
                     Defaults to ``False``.

        Returns:
            A Book with sections segmented by AI and ``character_registry``
            populated with all characters discovered during parsing
            (narrator always present). Contains at most ``chapter_limit``
            chapters (or all chapters when ``chapter_limit=0``).

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        # Step 1: Download the book
        logger.info("ai_workflow_started", url=url)
        if not self.downloader.parse(url):
            raise RuntimeError(f"Failed to download book from {url}")

        # Step 2: Find the downloaded HTML file
        downloader_book_id = self.downloader._extract_book_id(url)
        download_dir = f"books/{downloader_book_id}"

        html_file = self._find_html_file(download_dir)
        if not html_file:
            raise RuntimeError(f"No HTML file found in {download_dir}")

        logger.info("parsing_started", html_file=html_file)

        # Step 3: Read HTML content
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Step 4: Parse metadata (needed for book_id generation)
        metadata = self.metadata_parser.parse(html_content)

        # Step 4b: Check repository cache before expensive AI parse
        book_id = generate_book_id(metadata)

        if self._repository and not reparse:
            if self._repository.exists(book_id):
                cached = self._repository.load(book_id)
                if cached is not None:
                    logger.info("loaded_cached_parsed_book", book_id=book_id)
                    return cached

        # Step 5: Parse content
        content = self.content_parser.parse(html_content)

        # Step 6: Apply chapter limit (0 means all)
        chapters_to_segment = content.chapters
        if chapter_limit > 0:
            chapters_to_segment = content.chapters[:chapter_limit]

        logger.info(
            "ai_segmentation_started",
            title=metadata.title,
            total_chapters=len(content.chapters),
            chapter_limit=chapter_limit,
        )

        # Step 7: Segment sections using the AI section parser, threading
        # the CharacterRegistry and SceneRegistry through every call so IDs
        # remain consistent across the entire book.
        registry = CharacterRegistry.with_default_narrator()
        scene_registry = SceneRegistry()

        for chapter in chapters_to_segment:
            logger.info(
                "chapter_segmentation_started",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                section_count=len(chapter.sections),
            )
            for idx, section in enumerate(chapter.sections):
                # Pass all preceding sections within the same chapter as
                # context.  The AISectionParser caps the list to its own
                # configured context_window size, so no capping is needed here.
                # Context never crosses chapter boundaries.
                preceding = chapter.sections[:idx]
                section.segments, registry = self.section_parser.parse(
                    section, registry, context_window=preceding,
                    scene_registry=scene_registry,
                )

        # Step 8: Build voice_design_prompt for non-narrator characters
        # with sufficiently detailed descriptions (>= 10 words).
        _MIN_DESCRIPTION_WORDS = 10
        for char in registry.characters:
            if char.is_narrator:
                continue
            if char.description and len(char.description.split()) >= _MIN_DESCRIPTION_WORDS:
                desc = char.description.rstrip(".")
                char.voice_design_prompt = f"{char.age} {char.sex}, {desc}."
                logger.info(
                    "voice_design_prompt_set",
                    character_id=char.character_id,
                    voice_design_prompt=char.voice_design_prompt,
                )

        logger.info(
            "ai_workflow_complete",
            title=metadata.title,
            character_count=len(registry.characters),
        )

        # Step 9: Assemble and return Book with chapter_limit applied,
        # character_registry and scene_registry attached.
        content.chapters = chapters_to_segment
        book = Book(
            metadata=metadata,
            content=content,
            character_registry=registry,
            scene_registry=scene_registry,
        )

        # Step 10: Save to repository if available
        if self._repository:
            self._repository.save(book, book_id)
            logger.info("saved_parsed_book_to_repository", book_id=book_id)

        return book

    def _find_html_file(self, directory: str) -> Optional[str]:
        """Find the first HTML file in the directory recursively.

        Args:
            directory: Directory to search

        Returns:
            Path to HTML file, or None if not found
        """
        for root, _dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.html', '.htm')):
                    return os.path.join(root, filename)
        return None
