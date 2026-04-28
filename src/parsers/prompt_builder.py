"""Prompt builder for AI section parsing.

This module extracts prompt assembly logic from the section parser,
enabling the workflow layer to compose book context with parsing logic.

The static instructions are loaded from a template file at
``src/parsers/prompts/section_parser.prompt`` and rendered with computed
variables (type list, JSON example). The template contains no runtime
conditionals — the prompt is a single static source of truth shared with
promptfoo evals.
"""
import re
from pathlib import Path
from typing import Optional

from src.domain.models import (
    AIPrompt,
    CharacterRegistry,
    MoodRegistry,
    SceneRegistry,
    Section,
)

_TEMPLATE_DIR = Path(__file__).parent / "prompts"


def _render_template(template: str, variables: dict[str, object]) -> str:
    """Render a minimal template with ``{{ var }}`` substitutions.

    Only ``{{ var_name }}`` placeholders are supported; the template is
    otherwise static.
    """
    def _replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1).strip()
        return str(variables[var_name])

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", _replace_var, template)


class PromptBuilder:
    """Builds structured prompts for AI section parsing.

    Encapsulates the prompt assembly logic that was previously embedded in
    AISectionParser._build_prompt. The builder accepts book metadata at
    construction time and generates AIPrompt objects for each section.

    The builder is stateless except for book_title/book_author — it can be
    reused across multiple sections without side effects.
    """

    def __init__(
        self,
        book_title: Optional[str] = None,
        book_author: Optional[str] = None,
        context_window: int = 5,
    ):
        """Initialize the prompt builder.

        Args:
            book_title: Optional book title for context
            book_author: Optional book author for context
            context_window: Maximum number of preceding substantive sections to
                            include in the prompt as read-only context for
                            speaker inference. Noise-only sections
                            (other/illustration/copyright) are filtered before
                            capping. Defaults to 5.
        """
        self.book_title = book_title
        self.book_author = book_author
        self.context_window = context_window
        self._template = (_TEMPLATE_DIR / "section_parser.prompt").read_text()

    def build_prompt(
        self,
        text: str,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
        mood_registry: Optional[MoodRegistry] = None,
        current_open_mood_id: Optional[str] = None,
    ) -> AIPrompt:
        """Build a structured prompt for the AI model.

        Returns an AIPrompt that encapsulates the 6 logical parts of the beatation
        prompt, enabling cache-friendly API calls (e.g., AWS Bedrock prompt caching).

        Includes the current character registry so the AI can reuse IDs for
        known characters and emit new entries for genuinely new ones.

        When ``context_window`` is non-empty, a read-only surrounding-context
        block is included so the AI can resolve pronouns and infer turn-taking
        across section boundaries.

        When ``scene_registry`` is provided and non-empty, existing scenes are
        listed so the AI can reuse ``scene_id`` values instead of creating
        duplicates.

        Args:
            text: The section text to beat.
            registry: Current character registry for context.
            context_window: Optional neighbouring sections for speaker inference
                            (read-only — the AI must not re-beat them).
            scene_registry: Optional :class:`SceneRegistry` for scene reuse.

        Returns:
            An AIPrompt with beated static and dynamic portions.
        """
        # Render static instructions from template
        static_instructions = _render_template(self._template, {
            "type_list": self._build_type_list(),
            "json_example": self._build_json_example(),
        })

        # Build book context (title and author, varies per book)
        book_context = ""
        if self.book_title and self.book_author:
            book_context = (
                f"\n\nBook context: '{self.book_title}' "
                f"by {self.book_author}"
            )
        elif self.book_title:
            book_context = f"\n\nBook context: '{self.book_title}'"

        # Build character registry (varies per section)
        registry_lines = []
        for char in registry.characters:
            line = f'  - character_id: "{char.character_id}", name: "{char.name}"'
            if char.description:
                line += f', description: "{char.description}"'
            registry_lines.append(line)
        character_registry = "\n".join(registry_lines) if registry_lines else "  (empty)"
        character_registry += "\n"

        # Build surrounding context (varies per section)
        surrounding_context = ""
        if context_window:
            # Strip noise-only sections (other/illustration/copyright) so they
            # don't occupy slots in the window, then cap to the window size.
            substantive = [s for s in context_window if self._is_substantive(s)]
            capped = substantive[-self.context_window:] if self.context_window > 0 else []
        else:
            capped = []
        if capped:
            ctx_texts = "\n\n---\n\n".join(
                self._render_context_section(s) for s in capped
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

        # Build existing scenes block for scene reuse (varies per section)
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
                scene_registry_context = "\n".join(scene_lines)
                scene_registry_context = f"""
## Existing scenes (reuse these scene_ids when the setting matches)
{scene_registry_context}
"""

        # Build existing moods block for mood reuse (varies per section)
        mood_registry_context = self._render_mood_registry(
            mood_registry, current_open_mood_id,
        )

        return AIPrompt(
            static_instructions=static_instructions,
            book_context=book_context,
            character_registry=character_registry,
            surrounding_context=surrounding_context,
            scene_registry=scene_registry_context,
            mood_registry=mood_registry_context,
            text_to_parse=f"\nText to beat:\n{text}",
        )

    @staticmethod
    def _render_mood_registry(
        mood_registry: Optional[MoodRegistry],
        current_open_mood_id: Optional[str],
    ) -> str:
        """Render the known-moods slice for the section parser prompt.

        Lists the currently-open mood first (so the LLM can ``continue``) and
        up to two recently-closed moods as reference context. The registry
        itself stays compact — an exhaustive dump would flood the prompt.
        Returns an empty string when no moods are known yet.
        """
        if mood_registry is None:
            return ""
        moods = mood_registry.all()
        if not moods:
            return ""

        open_mood = None
        if current_open_mood_id is not None:
            open_mood = mood_registry.get(current_open_mood_id)

        recent_closed = [
            m for m in moods[-3:]
            if current_open_mood_id is None or m.mood_id != current_open_mood_id
        ]

        lines: list[str] = []
        if open_mood is not None:
            lines.append(
                f'  - mood_id: "{open_mood.mood_id}" (currently open), '
                f'description: "{open_mood.description}"'
            )
        for m in recent_closed:
            lines.append(
                f'  - mood_id: "{m.mood_id}", description: "{m.description}"'
            )
        if not lines:
            return ""
        return (
            "\n## Known story moods (reuse mood_id when continuing an arc)\n"
            + "\n".join(lines)
            + "\n"
        )

    @staticmethod
    def _build_type_list() -> str:
        """Build the beat type enumeration string."""
        return ", ".join([
            '"dialogue"',
            '"narration"',
            '"illustration"',
            '"copyright"',
            '"other"',
            '"sound_effect"',
            '"vocal_effect"',
        ])

    @staticmethod
    def _build_json_example() -> str:
        """Build the JSON example block."""
        return """\
{
  "beats": [
    {"type": "narration", "text": "She coughed loudly,", "emotion": "neutral", "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0},
    {"type": "sound_effect", "text": "dry cough", "sound_effect_detail": "harsh, dry cough from a middle-aged woman"},
    {"type": "narration", "text": "then turned to face the door.", "emotion": "neutral", "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0},
    {"type": "sound_effect", "text": "door knock", "sound_effect_detail": "4 firm knocks on a heavy old wooden door, echoing in a stone hallway"},
    {"type": "dialogue", "text": "A wizard, o' course,", "speaker": "hagrid", "emotion": "excited", "voice_stability": 0.35, "voice_style": 0.40, "voice_speed": 1.0}
  ],
  "new_characters": [
    {"character_id": "hagrid", "name": "Rubeus Hagrid", "sex": "male", "age": "adult", "description": "booming bass voice, thick West Country accent, warm and boisterous"}
  ],
  "character_description_updates": [
    {"character_id": "hagrid", "description": "booming bass voice, thick West Country accent; voice trembles when distressed"}
  ],
  "scene": {
    "environment": "indoor_quiet",
    "acoustic_hints": ["confined", "warm"],
    "voice_modifiers": {"stability_delta": 0.05, "style_delta": -0.05, "speed": 0.95},
    "ambient_prompt": "quiet drawing room, clock ticking, distant servant footsteps",
    "ambient_volume": -18.0
  },
  "mood": {"mood": "open", "description": "dry, wry social commentary; a knowing narrator setting the tone with gentle irony"}
}
"""

    @staticmethod
    def _is_substantive(section: Section) -> bool:
        """Return True if the section contains at least one dialogue or narration beat.

        Sections whose every beat is ``other``, ``illustration``, or
        ``copyright`` (e.g. bare footnote markers like ``{3}``) are noise and
        should be excluded from the context window so they don't consume slots
        that could hold real speaker-turn information.

        Unparsed sections (``beats`` is None or empty) are kept — we cannot
        tell whether they are substantive without parsing them.
        """
        if not section.beats:
            return True
        return any(seg.is_narratable for seg in section.beats)

    @staticmethod
    def _render_context_section(section: Section) -> str:
        """Render a section for inclusion in the context window prompt block.

        When the section has already been parsed (``beats`` is populated),
        each beat is prefixed with its resolved speaker so the LLM can
        infer turn-taking from labelled turns.  Narrator beats are emitted
        as plain text (no label).  Falls back to the raw ``section.text`` for
        sections that have not yet been parsed.

        Args:
            section: A preceding section, optionally with resolved beats.

        Returns:
            A human-readable string suitable for inclusion in the prompt.
        """
        if not section.beats:
            return section.text
        parts: list[str] = []
        for seg in section.beats:
            if seg.is_narratable:
                parts.append(f'[{seg.character_id}]: "{seg.text}"')
        return "\n".join(parts)
