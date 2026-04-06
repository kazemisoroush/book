"""AI-powered Project Gutenberg workflow for downloading and parsing books with section segmentation."""
import bisect
import os
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book, BookContent, CharacterRegistry, SceneRegistry
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

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        reparse: bool = False,
    ) -> Book:
        """Run the workflow to download, parse, and AI-segment a book.

        Supports incremental parsing with chapter-by-chapter flushing to repository.
        When a partial cached book exists, automatically resumes from the last
        cached chapter (transparent resume), regardless of start_chapter value.

        When a ``BookRepository`` was provided at construction time, each chapter
        is saved to the repository immediately after parsing (incremental flush).
        If the cache contains a partial book for this book_id and ``reparse`` is
        ``False``, the cached chapters are loaded and parsing continues from the
        first uncached chapter (or from start_chapter if it is after the last cached
        chapter).

        For each chapter being parsed, every section is passed through the AI
        section parser. Character and scene registries are threaded through all
        section parses so that IDs remain consistent across the entire book.

        Args:
            url: Project Gutenberg book URL (e.g.,
                 https://www.gutenberg.org/files/123/123-h.zip)
            start_chapter: 1-based chapter index to begin parsing (default: 1).
                           If a cached partial book exists and reparse=False,
                           auto-resumes from max(start_chapter, last_cached_chapter + 1).
            end_chapter: 1-based chapter index to end parsing (inclusive).
                         Default: None (parse all chapters in the book).
            reparse: When ``True``, bypass the cache and run the full AI
                     parse pipeline.  Each chapter is still saved to the
                     repository (overwriting any existing cached chapters).
                     Defaults to ``False``.

        Returns:
            A Book with sections segmented by AI and ``character_registry``
            populated with all characters discovered during parsing
            (narrator always present). Contains chapters from start_chapter
            to end_chapter (or all chapters when end_chapter=None).

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

        # Step 4b: Check repository cache for partial book (auto-resume)
        book_id = generate_book_id(metadata)
        book: Optional[Book] = None
        registry = CharacterRegistry.with_default_narrator()
        scene_registry = SceneRegistry()
        cached_chapter_numbers: set[int] = set()

        if self._repository and not reparse:
            if self._repository.exists(book_id):
                cached = self._repository.load(book_id)
                if cached is not None and cached.content.chapters:
                    book = cached
                    cached_chapter_numbers = {ch.number for ch in cached.content.chapters}
                    registry = cached.character_registry
                    scene_registry = cached.scene_registry
                    logger.info(
                        "resuming_from_cache",
                        book_id=book_id,
                        cached_chapter_numbers=sorted(cached_chapter_numbers),
                    )

        # Step 5: Parse content
        content = self.content_parser.parse(html_content)

        # Step 6: Determine end_chapter
        effective_end_chapter = end_chapter
        if effective_end_chapter is None:
            effective_end_chapter = len(content.chapters)

        logger.info(
            "ai_segmentation_started",
            title=metadata.title,
            total_chapters=len(content.chapters),
            start_chapter=start_chapter,
            effective_end_chapter=effective_end_chapter,
            cached_chapter_count=len(cached_chapter_numbers),
        )

        # Step 7: Initialize book if not loaded from cache
        if book is None:
            book = Book(
                metadata=metadata,
                content=BookContent(chapters=[]),
                character_registry=registry,
                scene_registry=scene_registry,
            )

        # Step 8: Segment sections using the AI section parser, threading
        # the CharacterRegistry and SceneRegistry through every call so IDs
        # remain consistent across the entire book.
        # Parse only chapters in [start_chapter, effective_end_chapter] that are not cached.
        for chapter in content.chapters:
            if chapter.number < start_chapter:
                continue
            if chapter.number > effective_end_chapter:
                break
            if chapter.number in cached_chapter_numbers:
                continue

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

            # Step 8b: Update registries and flush to repository
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

        # Step 10: Build voice_design_prompt for non-narrator characters
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
