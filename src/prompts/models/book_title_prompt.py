"""Concrete :class:`AIPrompt` for book-title announcement formatting."""
from dataclasses import dataclass
from typing import ClassVar, Optional

from src.prompts.models.ai_prompt import AIPrompt, load_template


@dataclass(frozen=True)
class BookTitleAnnouncementPrompt(AIPrompt):
    """Prompt that asks the LLM to render a book title for spoken narration.

    Static portion: the instruction template (shared across all books).
    Dynamic portion: the raw title and author for this specific book.
    """

    TEMPLATE_FILENAME: ClassVar[str] = "book_title.prompt"
    _TEMPLATE: ClassVar[str] = load_template("book_title.prompt")

    title: str
    author: Optional[str]

    def build_static_portion(self) -> str:
        return self._TEMPLATE

    def build_dynamic_portion(self) -> str:
        return (
            f"Title: {self.title or 'Untitled'}\n"
            f"Author: {self.author or 'Unknown'}"
        )
