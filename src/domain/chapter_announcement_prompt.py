"""Concrete :class:`AIPrompt` for chapter-announcement formatting."""
from dataclasses import dataclass

from src.domain.ai_prompt import AIPrompt


@dataclass(frozen=True)
class ChapterAnnouncementPrompt(AIPrompt):
    """Prompt that asks the LLM to render a chapter announcement for narration.

    Static portion: the instruction template (shared across all chapters).
    Dynamic portion: this chapter's number and title.
    """

    static_instructions: str
    chapter_number: int
    chapter_title: str

    def build_static_portion(self) -> str:
        return self.static_instructions

    def build_dynamic_portion(self) -> str:
        return (
            f"Chapter number: {self.chapter_number}\n"
            f"Chapter title: {self.chapter_title}"
        )
