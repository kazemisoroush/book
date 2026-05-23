"""Concrete :class:`AIPrompt` for AI section parsing."""
from dataclasses import dataclass

from src.domain.ai_prompt import AIPrompt


@dataclass(frozen=True)
class SectionParserPrompt(AIPrompt):
    """Prompt for the AI section parser.

    Composed of 7 logical parts split into a cacheable static portion
    (instructions + book context) and a per-section dynamic portion
    (registries, surrounding context, text to parse).
    """

    static_instructions: str
    book_context: str
    character_registry: str
    surrounding_context: str
    scene_registry: str
    text_to_parse: str
    mood_registry: str = ""

    def build_static_portion(self) -> str:
        return self.static_instructions + self.book_context

    def build_dynamic_portion(self) -> str:
        return (
            self.character_registry
            + self.surrounding_context
            + self.scene_registry
            + self.mood_registry
            + self.text_to_parse
        )
