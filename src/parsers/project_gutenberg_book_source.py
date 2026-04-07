"""Concrete BookSource for Project Gutenberg HTML books.

Composes: BookDownloader, BookMetadataParser, BookContentParser, and
(optionally) BookRepository.  Absorbs download/parse/cache/resume logic
that previously lived in the workflow layer.
"""
from typing import Optional

import structlog

from src.domain.models import (
    Book,
    BookContent,
    BookParseContext,
    CharacterRegistry,
    SceneRegistry,
)
from src.downloader.book_downloader import BookDownloader
from src.parsers.book_content_parser import BookContentParser
from src.parsers.book_metadata_parser import BookMetadataParser
from src.parsers.book_source import BookSource
from src.repository.book_id import generate_book_id
from src.repository.book_repository import BookRepository

logger = structlog.get_logger(__name__)


class ProjectGutenbergBookSource(BookSource):
    """BookSource backed by a Project Gutenberg downloader and static parsers."""

    def __init__(
        self,
        downloader: BookDownloader,
        metadata_parser: BookMetadataParser,
        content_parser: BookContentParser,
        repository: Optional[BookRepository] = None,
    ) -> None:
        self._downloader = downloader
        self._metadata_parser = metadata_parser
        self._content_parser = content_parser
        self._repository = repository

    def get_book(self, url: str) -> Book:
        """Download, parse metadata + content, return a Book (no AI, no caching)."""
        logger.info("book_source_download_started", url=url)
        html_content = self._downloader.download(url)

        metadata = self._metadata_parser.parse(html_content)
        content = self._content_parser.parse(html_content)

        logger.info(
            "book_source_parse_complete",
            title=metadata.title,
            chapters=len(content.chapters),
        )
        return Book(metadata=metadata, content=content)

    def get_book_for_segmentation(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        reparse: bool = False,
    ) -> BookParseContext:
        """Download, parse, check cache, and return a segmentation-ready context."""
        logger.info("book_source_segmentation_started", url=url)
        html_content = self._downloader.download(url)

        metadata = self._metadata_parser.parse(html_content)
        content = self._content_parser.parse(html_content)

        # Check repository cache
        book_id = generate_book_id(metadata)
        book: Optional[Book] = None
        cached_chapter_numbers: set[int] = set()

        if self._repository and not reparse:
            if self._repository.exists(book_id):
                cached = self._repository.load(book_id)
                if cached is not None and cached.content.chapters:
                    book = cached
                    cached_chapter_numbers = {ch.number for ch in cached.content.chapters}
                    logger.info(
                        "resuming_from_cache",
                        book_id=book_id,
                        cached_chapter_numbers=sorted(cached_chapter_numbers),
                    )

        # Initialize book if not loaded from cache
        if book is None:
            book = Book(
                metadata=metadata,
                content=BookContent(chapters=[]),
                character_registry=CharacterRegistry.with_default_narrator(),
                scene_registry=SceneRegistry(),
            )

        # Determine effective end chapter
        effective_end_chapter = end_chapter if end_chapter is not None else len(content.chapters)

        # Build list of chapters that need parsing
        chapters_to_parse = [
            chapter
            for chapter in content.chapters
            if start_chapter <= chapter.number <= effective_end_chapter
            and chapter.number not in cached_chapter_numbers
        ]

        logger.info(
            "book_source_segmentation_context_ready",
            title=metadata.title,
            total_chapters=len(content.chapters),
            chapters_to_parse=len(chapters_to_parse),
            cached_chapters=len(cached_chapter_numbers),
        )

        return BookParseContext(
            book=book,
            chapters_to_parse=chapters_to_parse,
            content=content,
        )
