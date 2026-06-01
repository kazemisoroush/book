"""Fluent builder for the ``chapter_parser`` prompt."""
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Optional

from src.prompts.chapter_parser.input import PromptInput
from src.prompts.prompt_builder import PromptBuilder

_TEMPLATE_PATH = Path(__file__).parent / "chapter_parser.prompt"

DEFAULT_ALLOWED_BEAT_TYPES = [
    "narration",
    "dialogue",
    "book_title_announcement",
    "chapter_announcement",
    "sound_effect",
    "vocal_effect",
    "illustration",
    "copyright",
    "other",
]


@dataclass(frozen=True)
class ChapterParserPromptBuilder(PromptBuilder):
    """Fluent builder for ``chapter_parser.prompt``."""

    chapter: Optional[PromptInput] = None
    allowed_beat_types: list[str] = field(
        default_factory=lambda: list(DEFAULT_ALLOWED_BEAT_TYPES)
    )

    def with_chapter(self, chapter: PromptInput) -> "ChapterParserPromptBuilder":
        return replace(self, chapter=chapter)

    def with_allowed_beat_types(
        self, beat_types: list[str]
    ) -> "ChapterParserPromptBuilder":
        return replace(self, allowed_beat_types=list(beat_types))

    def build(self) -> str:
        if self.chapter is None:
            raise ValueError(
                "ChapterParserPromptBuilder requires .with_chapter(...) before .build()"
            )
        template = _TEMPLATE_PATH.read_text()
        beat_types_block = "\n".join(f"- {t}" for t in self.allowed_beat_types)
        chapter_json = json.dumps(asdict(self.chapter), indent=2)
        return (
            template
            .replace("{{ INPUT_ALLOWED_BEAT_TYPES }}", beat_types_block)
            .replace("{{ INPUT_CHAPTER }}", chapter_json)
        )
