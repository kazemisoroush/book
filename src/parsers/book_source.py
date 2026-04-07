"""Abstract interface for obtaining a parsed Book from a source URL.

A ``BookSource`` encapsulates the entire download → parse → cache pipeline
so that workflow classes remain pure orchestrators.  Concrete implementations
compose a downloader, metadata parser, content parser, and (optionally) a
repository for caching.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import Book, BookParseContext


class BookSource(ABC):

    @abstractmethod
    def get_book(self, url: str) -> Book:
        """Download, parse, and return a complete Book (no AI segmentation)."""

    @abstractmethod
    def get_book_for_segmentation(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        reparse: bool = False,
    ) -> BookParseContext:
        """Return a BookParseContext ready for the AI segmentation loop.

        The returned context contains:
        - ``book``: The Book (from cache or freshly constructed with empty chapters).
                     Registries are on ``book.character_registry`` / ``book.scene_registry``.
        - ``chapters_to_parse``: Only the uncached chapters in the requested range.
        - ``content``: The full parsed BookContent (all chapters).
        """
