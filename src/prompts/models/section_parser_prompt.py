"""Concrete :class:`AIPrompt` for AI section parsing.

The static instructions are loaded from
``src/prompts/templates/section_parser.prompt`` and shared verbatim with
promptfoo evals so the application and evals always see the same prompt.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.domain.models import (
    CharacterRegistry,
    SceneRegistry,
    Section,
)
from src.prompts.models.ai_prompt import AIPrompt

_TEMPLATE = (
    Path(__file__).resolve().parent.parent / "templates" / "section_parser.prompt"
).read_text()


@dataclass(frozen=True)
class SectionParserPrompt(AIPrompt):
    """Prompt for the AI section parser.

    Composed of logical parts split into a cacheable static portion
    (instructions + book context) and a per-section dynamic portion
    (registries, surrounding context, text to parse).
    """

    static_instructions: str
    book_context: str
    character_registry: str
    surrounding_context: str
    scene_registry: str
    text_to_parse: str

    def build_static_portion(self) -> str:
        return self.static_instructions + self.book_context

    def build_dynamic_portion(self) -> str:
        return (
            self.character_registry
            + self.surrounding_context
            + self.scene_registry
            + self.text_to_parse
        )

    @classmethod
    def create(
        cls,
        text: str,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        book_title: Optional[str] = None,
        book_author: Optional[str] = None,
        scene_registry: Optional[SceneRegistry] = None,
        window_size: int = 5,
    ) -> "SectionParserPrompt":
        """Assemble a :class:`SectionParserPrompt` for one section.

        Args:
            text: The section text to beat.
            registry: Current character registry (rendered into the prompt).
            context_window: Optional preceding sections for speaker inference.
                Noise-only sections (other/illustration/copyright) are filtered
                out before capping; the last *window_size* substantive sections
                are kept.
            book_title: Optional book title; rendered into the static-cacheable
                portion alongside the instructions.
            book_author: Optional book author; rendered with the title.
            scene_registry: Optional :class:`SceneRegistry` for scene reuse.
            window_size: Maximum number of substantive preceding sections to
                include. Default 5.
        """
        book_context = ""
        if book_title and book_author:
            book_context = f"\n\nBook context: '{book_title}' by {book_author}"
        elif book_title:
            book_context = f"\n\nBook context: '{book_title}'"

        registry_lines = []
        for char in registry.characters:
            line = f'  - character_id: "{char.character_id}", name: "{char.name}"'
            if char.description:
                line += f', description: "{char.description}"'
            registry_lines.append(line)
        character_registry = "\n".join(registry_lines) if registry_lines else "  (empty)"
        character_registry += "\n"

        surrounding_context = ""
        if context_window:
            substantive = [s for s in context_window if _is_substantive(s)]
            capped = substantive[-window_size:] if window_size > 0 else []
            if capped:
                ctx_texts = "\n\n---\n\n".join(
                    _render_context_section(s) for s in capped
                )
                surrounding_context = f"""
## Surrounding context (for speaker inference only — do not beat)
The following sections appear immediately before the target text.
Use them for context only to resolve speakers, pronouns, and turn-taking.
If you can identify the speaker of a dialogue from this context, do so:
add them to new_characters if they are not already in the character list above.

{ctx_texts}

---
"""

        scene_registry_context = ""
        if scene_registry is not None:
            existing_scenes = scene_registry.all()
            if existing_scenes:
                scene_lines = []
                for sc in existing_scenes:
                    line = f'  - scene_id: "{sc.scene_id}", environment: "{sc.environment}"'
                    if sc.acoustic_hints:
                        line += f', acoustic_hints: {sc.acoustic_hints}'
                    scene_lines.append(line)
                scene_registry_context = (
                    "\n## Existing scenes (reuse these scene_ids when the setting matches)\n"
                    + "\n".join(scene_lines)
                    + "\n"
                )

        return cls(
            static_instructions=_TEMPLATE,
            book_context=book_context,
            character_registry=character_registry,
            surrounding_context=surrounding_context,
            scene_registry=scene_registry_context,
            text_to_parse=f"\nText to beat:\n{text}",
        )


def _is_substantive(section: Section) -> bool:
    """Return True if the section contains at least one dialogue or narration beat.

    Sections whose every beat is ``other``, ``illustration``, or ``copyright``
    (e.g. bare footnote markers like ``{3}``) are noise and excluded from the
    context window. Unparsed sections (``beats`` is None or empty) are kept —
    substantiveness can't be determined without parsing them first.
    """
    if not section.beats:
        return True
    return any(seg.is_narratable for seg in section.beats)


def _render_context_section(section: Section) -> str:
    """Render a section for inclusion in the context-window prompt block.

    Parsed sections render each beat prefixed with its resolved speaker so the
    LLM can infer turn-taking from labelled turns. Unparsed sections fall back
    to the raw ``section.text``.
    """
    if not section.beats:
        return section.text
    parts: list[str] = []
    for seg in section.beats:
        if seg.is_narratable:
            parts.append(f'[{seg.character_id}]: "{seg.text}"')
    return "\n".join(parts)
