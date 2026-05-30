"""Concrete :class:`AIPrompt` for chapter-announcement formatting."""
from dataclasses import dataclass
from typing import ClassVar

from src.prompts.models.ai_prompt import AIPrompt, load_template


@dataclass(frozen=True)
class ChapterAnnouncementPrompt(AIPrompt):
    """Prompt that asks the LLM to render a chapter announcement for narration.

    Static portion: the instruction template (shared across all chapters).
    Dynamic portion: this chapter's number and title.
    """

    TEMPLATE_FILENAME: ClassVar[str] = "chapter_announcement.prompt"
    _TEMPLATE: ClassVar[str] = load_template("chapter_announcement.prompt")

    chapter_number: int
    chapter_title: str

    def build_static_portion(self) -> str:
        return self._TEMPLATE

    def build_dynamic_portion(self) -> str:
        return (
            f"Chapter number: {self.chapter_number}\n"
            f"Chapter title: {self.chapter_title}"
        )
