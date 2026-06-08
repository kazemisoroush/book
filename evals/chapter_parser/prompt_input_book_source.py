"""BookSource that wraps a PromptInput as the source for AIWorkflow."""
from typing import Optional

from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    BookParseContext,
    Chapter,
    Section,
)
from src.parsers.book_source import BookSource
from src.prompts.chapter_parser.input import PromptInput

_SKIP_SECTION_TYPES = {"book_title_announcement", "chapter_announcement"}


class PromptInputBookSource(BookSource):
    """Expose a PromptInput as a BookSource for the chapter_parser eval."""

    def __init__(self, prompt_input: PromptInput) -> None:
        self._prompt_input = prompt_input

    def get_book(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> BookParseContext:
        metadata = BookMetadata(
            title=self._prompt_input.metadata.title,
            author=self._prompt_input.metadata.author or None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )
        chapters = [
            Chapter(
                number=pi_chapter.id,
                title="",
                sections=[
                    Section(text=s.text, section_type=s.type)
                    for s in pi_chapter.sections
                    if s.type not in _SKIP_SECTION_TYPES
                ],
            )
            for pi_chapter in self._prompt_input.chapters
        ]
        content = BookContent(chapters=list(chapters))
        book = Book(metadata=metadata, content=content)
        return BookParseContext(
            book=book,
            chapters_to_parse=list(chapters),
            content=content,
        )
