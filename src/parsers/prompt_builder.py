"""Prompt builder for AI section parsing.

This module extracts prompt assembly logic from the section parser,
enabling the workflow layer to compose book context with parsing logic.
"""
from typing import Optional
from src.domain.models import (
    AIPrompt, CharacterRegistry, Section, SceneRegistry,
)


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

    def build_prompt(
        self,
        text: str,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> AIPrompt:
        """Build a structured prompt for the AI model.

        Returns an AIPrompt that encapsulates the 6 logical parts of the segmentation
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
            text: The section text to segment.
            registry: Current character registry for context.
            context_window: Optional neighbouring sections for speaker inference
                            (read-only — the AI must not re-segment them).
            scene_registry: Optional :class:`SceneRegistry` for scene reuse.

        Returns:
            An AIPrompt with segmented static and dynamic portions.
        """
        # Build static instructions (immutable rules and format)
        static_instructions = """Break down the following text into segments \
alternating between narration and dialogue.

## Existing characters (reuse these IDs — do NOT create duplicates)
"""

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
## Surrounding context (for speaker inference only — do not segment)
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

        # Build the continuation of static instructions (with JSON examples and rules)
        static_instructions_continuation = """\
For each segment, identify:
- type: "dialogue", "narration", "illustration", "copyright", "other", "sound_effect", "vocal_effect", or "chapter_announcement"
- text: the actual text content (without quotes for dialogue)
- speaker: the character_id for dialogue (use existing IDs from the list \
above when possible; use null if unknown)
- emotion: an audio tag describing the vocal delivery at this moment. \
Must be auditory — a vocal quality, sound, or delivery style \
(e.g. whispers, sighs, laughs, sarcastic, excited, crying, curious). \
Be as specific and nuanced as possible: prefer precise labels like \
"frustrated", "seething", "bitter", "wistful", "hesitant", "pleading", \
"incredulous", "resigned", "defiant", "trembling", "guarded", "awed" \
over generic ones like "angry" or "sad". \
Do NOT use visual actions (grinning, standing, pacing). \
Use "neutral" for narration and for dialogue with no discernible \
emotional charge. \
Split aggressively at emotional inflection points: if the tone shifts \
at all mid-utterance — even subtly — split into separate segments. \
For example, if a character starts calm and becomes agitated within a \
single line of dialogue, split at the vocal shift point so each \
sub-segment gets its own emotion and voice settings.
- voice_stability: float 0.0–1.0 controlling vocal consistency. Use this table as a guide:
  * 0.65 — narration, neutral dialogue, exposition (stable, even delivery)
  * 0.50 — curious, thoughtful, calm, gentle (slight variation)
  * 0.35 — angry, sad, happy, excited (expressive, varied)
  * 0.25 — screaming, sobbing, furious, ecstatic (highly varied)
  * 0.45 — whispered, intimate, hushed (controlled but soft)
- voice_style: float 0.0–1.0 controlling expressiveness. Use this table as a guide:
  * 0.05 — narration, neutral dialogue (minimal style)
  * 0.20 — curious, thoughtful, calm (mild expressiveness)
  * 0.40 — angry, sad, happy, excited (moderate expressiveness)
  * 0.60 — screaming, sobbing, furious, ecstatic (high expressiveness)
  * 0.30 — whispered, intimate, hushed
- voice_speed: float controlling speaking rate. Use this table as a guide:
  * 1.0  — normal speech
  * 0.90 — whispered, intimate, hushed (slower)
  * 1.05 — screaming, ecstatic, desperate (slightly faster)

Use "other" for non-narratable content like page numbers (e.g. {6}), \
metadata markers, or any text that should not be read aloud.

**Sound effects (US-023):** When the text explicitly mentions a diegetic sound event \
(a cough, a knock, thunder, etc.), output a SOUND_EFFECT segment at the position \
where the sound occurs. Evidence-based only: do NOT invent sounds. Only explicit \
textual mentions trigger sound effects. Provide both a short label (text) and an optional \
detailed description (sound_effect_detail).

**Vocal effects (US-017):** When the narrative implies a character makes a \
non-speech vocal sound (breath intake/exhale, cough, sigh, gasp, laugh, sob, \
throat clear, sneeze, groan, etc.), output a segment with \
`type: "vocal_effect"`, `text` describing the sound in 1-5 words \
(e.g., "soft breath intake", "dry persistent cough", "quiet nervous laughter"), \
and `speaker` set to the character making the sound. Only include vocal effects \
for sounds the narrative **explicitly implies** or describes. \
Do NOT invent sounds that are not textually supported.

**Chapter announcements (US-029):** Output a `type: "chapter_announcement"` segment \
as the **first** segment of each chapter. The text should state the chapter number \
and title in a natural, spoken form (e.g., "Chapter One." or "Chapter One. The Beginning."). \
When the chapter has no meaningful title (e.g., just "Chapter 1"), keep it short. \
Set `speaker: "narrator"` and omit emotion and voice modifiers. \
Only emit one chapter_announcement per chapter, always first.

If you discover a new character not yet in the list, add them to \
"new_characters".

Return ONLY a JSON object in this exact format:
{
  "segments": [
    {"type": "chapter_announcement", "text": "Chapter One. The Invitation.", "speaker": "narrator"},
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
  }
}

Rules:
- Strip quotation marks from dialogue text
- Keep narration text exactly as written
- Strip trailing punctuation that is not a sentence terminator (. ! ?) from \
segment text. Commas, semicolons, colons, em-dashes, en-dashes, ellipses, and \
hyphens must not appear at the end of any segment's text
- Reuse existing character_id values from the list above for known characters
- Only add to new_characters for genuinely new speakers not already listed
- For each new character, infer "sex" ("male", "female", or null if unknown) \
and "age" ("young", "adult", "elderly", or null if unknown) from context
- **New characters:** For each new character, add a "description": 2–3 sentences \
(at least 100 characters) describing their voice and manner of speaking — include \
vocal quality (pitch, roughness, warmth), accent if evident, pace, and personality \
as expressed in speech. Be specific and detailed. \
If nothing can be inferred from context, omit the field entirely (do not guess)
- **Existing characters:** If this section reveals meaningfully new information \
about how an existing character sounds or speaks, add an entry to \
character_description_updates with a revised "description" that synthesises what \
was known before with what is new. Only include entries where there is genuine new \
vocal information; omit the character otherwise. If no updates, return an empty array
- If context window sections identify a speaker, use that — infer from \
turn-taking, pronouns, and names mentioned in adjacent sections
- Dialogue is a ping-pong exchange: consecutive quoted lines almost always \
alternate between speakers. If speaker A just spoke and you are uncertain \
who speaks next, strongly prefer speaker B over speaker A
- **Scene / environment detection:** Identify the physical setting or acoustic \
environment of the text. Set the "scene" key with:
  * "environment": a short label for the physical setting (e.g. "outdoor_open", \
"indoor_quiet", "cave", "tunnel", "car", "vehicle", "battlefield", "whisper_scene", \
"forest", "street", "church"). Use snake_case. If the setting is unclear or generic, \
use "indoor_quiet" as default.
  * "acoustic_hints": a list of acoustic properties (e.g. "echo", "confined", \
"quiet", "loud", "open", "reverberant", "intimate", "windy"). Empty list if none apply.
  * "voice_modifiers": a dict of additive voice-setting adjustments for the scene. Keys:
    - "stability_delta": float delta on voice stability (e.g. -0.05 = less stable/more expressive, \
+0.05 = more stable/controlled). Use 0.0 for no change.
    - "style_delta": float delta on style/expressiveness (e.g. +0.15 = more expressive, \
-0.10 = more restrained). Use 0.0 for no change.
    - "speed": absolute speaking rate (e.g. 0.90 = slower, 1.10 = faster, 1.0 = normal). \
Examples by environment:
      * outdoor_open: {"stability_delta": 0.0, "style_delta": 0.05, "speed": 1.0}
      * indoor_quiet: {"stability_delta": 0.05, "style_delta": -0.05, "speed": 0.95}
      * cave/tunnel: {"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90}
      * car/vehicle: {"stability_delta": 0.05, "style_delta": 0.0, "speed": 1.0}
      * battlefield: {"stability_delta": -0.10, "style_delta": 0.15, "speed": 1.10}
      * whisper_scene: {"stability_delta": 0.10, "style_delta": -0.10, "speed": 0.85}
    Use these examples as guidance; adapt to the specific context of the scene. \
If there is no clear physical setting at all, omit the "scene" key entirely.
  * "ambient_prompt": a natural-language description of the environmental background \
sound for this scene (e.g. "quiet drawing room, clock ticking, distant servant footsteps", \
"wind howling across open moor, distant thunder", "crackling campfire, crickets chirping"). \
Describe only environmental sounds, not music or speech. If no ambient sound fits, use null.
  * "ambient_volume": mix level in dB relative to speech. Quieter for intimate settings \
(e.g. -20.0), louder for busy/action environments (e.g. -16.0). Typical value is -18.0. \
Use null if ambient_prompt is null.
- Return valid JSON only, no other text
"""

        return AIPrompt(
            static_instructions=static_instructions + static_instructions_continuation,
            book_context=book_context,
            character_registry=character_registry,
            surrounding_context=surrounding_context,
            scene_registry=scene_registry_context,
            text_to_segment=f"\nText to segment:\n{text}",
        )

    @staticmethod
    def _is_substantive(section: Section) -> bool:
        """Return True if the section contains at least one dialogue or narration segment.

        Sections whose every segment is ``other``, ``illustration``, or
        ``copyright`` (e.g. bare footnote markers like ``{3}``) are noise and
        should be excluded from the context window so they don't consume slots
        that could hold real speaker-turn information.

        Unparsed sections (``segments`` is None or empty) are kept — we cannot
        tell whether they are substantive without parsing them.
        """
        if not section.segments:
            return True
        return any(seg.is_narratable for seg in section.segments)

    @staticmethod
    def _render_context_section(section: Section) -> str:
        """Render a section for inclusion in the context window prompt block.

        When the section has already been parsed (``segments`` is populated),
        each segment is prefixed with its resolved speaker so the LLM can
        infer turn-taking from labelled turns.  Narrator segments are emitted
        as plain text (no label).  Falls back to the raw ``section.text`` for
        sections that have not yet been parsed.

        Args:
            section: A preceding section, optionally with resolved segments.

        Returns:
            A human-readable string suitable for inclusion in the prompt.
        """
        if not section.segments:
            return section.text
        parts: list[str] = []
        for seg in section.segments:
            if seg.is_narratable:
                parts.append(f'[{seg.character_id}]: "{seg.text}"')
        return "\n".join(parts)
