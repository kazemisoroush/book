"""Concrete :class:`AIPrompt` for book-title announcement formatting."""
from dataclasses import dataclass
from typing import Optional

from src.domain.ai_prompt import AIPrompt


@dataclass(frozen=True)
class BookTitleAnnouncementPrompt(AIPrompt):
    """Prompt that asks the LLM to render a book title for spoken narration.

    Static portion: the instruction template (shared across all books).
    Dynamic portion: the raw title and author for this specific book.
    """

    static_instructions: str
    title: str
    author: Optional[str]

    def build_static_portion(self) -> str:
        return self.static_instructions

    def build_dynamic_portion(self) -> str:
        return (
            f"Title: {self.title or 'Untitled'}\n"
            f"Author: {self.author or 'Unknown'}"
        )
