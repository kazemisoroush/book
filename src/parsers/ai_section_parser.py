"""AI-powered section parser that segments text into dialogue and narration."""
import json
import re
import time
from dataclasses import replace as dc_replace
from typing import Optional
import structlog
from src.ai.ai_provider import AIProvider
from src.parsers.book_section_parser import BookSectionParser
from src.domain.models import (
    Section, Segment, SegmentType, CharacterRegistry, Character, Scene,
    SceneRegistry, AIPrompt,
)

_MAX_RETRIES = 3
_RETRY_DELAY = 1.0

logger = structlog.get_logger(__name__)


def _repair_json(text: str) -> str:
    """Repair common JSON formatting issues in LLM output.

    Handles three types of broken JSON:
    1. Raw newlines/tabs inside string values (escaped to \\n, \\t)
    2. Trailing commas before ] or } (removed)
    3. Truncated output with unterminated strings or brackets (closed gracefully)

    Args:
        text: Potentially broken JSON text

    Returns:
        Repaired JSON that can be parsed
    """
    # Remove trailing commas before ] or }
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Escape unescaped newlines and tabs inside strings
    # This is a best-effort approach: find quoted strings and escape internal newlines
    def escape_string_contents(match: re.Match) -> str:
        """Escape newlines and tabs inside matched string."""
        s = match.group(1)
        # Replace unescaped newlines with \n (but not already escaped ones)
        s = re.sub(r'(?<!\\)\n', r'\\n', s)
        s = re.sub(r'(?<!\\)\t', r'\\t', s)
        return '"' + s + '"'

    # Match quoted strings (but this is tricky with actual embedded newlines)
    # Simpler approach: replace literal newlines not inside strings with spaces
    lines = text.split('\n')
    result_lines = []
    in_string = False
    for line in lines:
        if not in_string:
            # Count quotes to see if we're starting a string
            result_lines.append(line)
        else:
            # We're continuing a multi-line string
            result_lines[-1] += '\\n' + line

        # Count unescaped quotes to track string state
        unescaped_quotes = len(re.findall(r'(?<!\\)"', line))
        if unescaped_quotes % 2 == 1:
            in_string = not in_string

    text = '\n'.join(result_lines)

    # Close any unclosed brackets
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    open_quotes = len(re.findall(r'(?<!\\)"', text)) % 2

    # Close unclosed quotes if needed
    if open_quotes == 1:
        text = text.rstrip() + '"'

    # Close unclosed brackets
    if open_brackets > 0:
        text = text.rstrip() + ']' * open_brackets

    # Close unclosed braces
    if open_braces > 0:
        text = text.rstrip() + '}' * open_braces

    return text


class AISectionParser(BookSectionParser):
    """Uses AI to intelligently segment sections into dialogue and narration.

    This parser leverages LLMs to:
    - Identify dialogue vs narration
    - Determine speakers for dialogue segments, using existing registry IDs
    - Emit new character entries for previously-unseen characters, including
      a vocal ``description`` (pitch, accent, manner of speaking) when inferable
    - Progressively enrich existing characters via ``character_description_updates``
      returned by the AI when a section reveals new vocal information
    - Handle complex cases like interrupted dialogue and nested quotes

    The registry is threaded through each call so that character IDs remain
    consistent across the full book.  Description updates are applied to the
    registry immediately after each section so that subsequent sections see the
    accumulated description when their prompts are built.

    Short-circuit rules (no LLM call made):
    - Sections with ``section_type`` already set (e.g. ``"illustration"``) are
      passed through as a single segment of the corresponding type.
    - Sections with empty text are skipped and return an empty segment list.

    Follows SOLID principles:
    - Single Responsibility: Only segments sections using AI
    - Dependency Inversion: Depends on AIProvider abstraction
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        book_title: Optional[str] = None,
        book_author: Optional[str] = None,
        context_window: int = 5,
    ):
        """Initialize the AI section parser.

        Args:
            ai_provider: The AI provider to use for segmentation
            book_title: Optional book title for context
            book_author: Optional book author for context
            context_window: Maximum number of preceding substantive sections to
                            include in the prompt as read-only context for
                            speaker inference.  Noise-only sections
                            (other/illustration/copyright) are filtered before
                            capping.  Defaults to 5.
        """
        self.ai_provider = ai_provider
        self.book_title = book_title
        self.book_author = book_author
        self.context_window = context_window
        self.last_detected_scene: Optional[Scene] = None

    def parse(  # type: ignore[override]
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> tuple[list[Segment], CharacterRegistry]:
        """Parse a section into segments using AI.

        Includes the current registry in the prompt so the AI can reuse
        existing character IDs and emit new ones.  Any new characters
        returned by the AI are upserted into the registry before returning.

        When *scene_registry* is provided, detected scenes are upserted into
        it and each returned segment receives a ``scene_id`` referencing the
        scene in the registry.

        Retries up to _MAX_RETRIES times on empty or unparseable responses
        before raising.

        Args:
            section: The section to parse.
            registry: The current character registry.  Used for prompt
                      context and updated with any new characters discovered.
            context_window: Optional list of neighbouring sections (typically
                            up to 5 preceding sections) provided as read-only
                            context for speaker inference.  These are included
                            in the prompt but the AI must not re-segment them.
            scene_registry: Optional :class:`SceneRegistry` threaded through
                            parsing.  When provided, detected scenes are
                            upserted and ``scene_id`` is set on segments.

        Returns:
            Tuple of (segments, updated_registry).

        Raises:
            ValueError: If the AI response cannot be parsed after all retries
            Exception: If the AI provider fails
        """
        # Short-circuit: sections with a pre-resolved type skip the LLM call.
        if section.section_type is not None:
            self.last_detected_scene = None
            valid_values = {t.value for t in SegmentType}
            seg_type = (
                SegmentType(section.section_type)
                if section.section_type in valid_values
                else SegmentType.OTHER
            )
            return [Segment(text=section.text, segment_type=seg_type)], registry

        # Short-circuit: empty text sections skip the LLM call entirely.
        if not section.text.strip():
            self.last_detected_scene = None
            return [], registry

        prompt = self._build_prompt(section.text, registry, context_window,
                                    scene_registry=scene_registry)
        last_error: Exception = ValueError("No attempts made")
        text_preview = section.text[:60].replace("\n", " ")
        for attempt in range(_MAX_RETRIES):
            response = self.ai_provider.generate(prompt, max_tokens=8192)
            if not response.strip():
                last_error = ValueError("Empty response from AI provider")
                logger.warning(
                    "ai_section_parser_empty_response",
                    attempt=attempt + 1,
                    max_retries=_MAX_RETRIES,
                    text_preview=text_preview,
                )
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
                continue
            try:
                segments, new_characters, description_updates, detected_scene = self._parse_response(response)
                self.last_detected_scene = detected_scene

                # Upsert scene into registry and stamp scene_id on segments
                if detected_scene is not None and scene_registry is not None:
                    scene_registry.upsert(detected_scene)
                    for seg in segments:
                        seg.scene_id = detected_scene.scene_id

                for char in new_characters:
                    registry.upsert(char)
                # Apply description updates for existing characters
                for char_id, new_description in description_updates:
                    existing = registry.get(char_id)
                    if existing is not None:
                        registry.upsert(dc_replace(existing, description=new_description))
                logger.debug(
                    "ai_section_parsed",
                    segment_count=len(segments),
                    new_character_count=len(new_characters),
                    description_update_count=len(description_updates),
                    text_preview=text_preview,
                )
                return segments, registry
            except ValueError as e:
                last_error = e
                logger.warning(
                    "ai_section_parser_parse_error",
                    attempt=attempt + 1,
                    max_retries=_MAX_RETRIES,
                    error=str(e),
                    text_preview=text_preview,
                )
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
        logger.error(
            "ai_section_parser_failed",
            max_retries=_MAX_RETRIES,
            error=str(last_error),
            text_preview=text_preview,
        )
        raise last_error

    def _build_prompt(
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
- type: "dialogue", "narration", "illustration", "copyright", or "other"
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
- sound_effect_description: optional string describing a diegetic sound effect for \
explicit narrative actions (US-023). Only include if the text **explicitly** names \
a sound-worthy action (e.g., "she coughed" → "dry cough", "a knock at the door" → \
"firm knock on wooden door"). DO NOT invent or hallucinate sounds. If there is no \
explicit sound-worthy action, use null.

Use "other" for non-narratable content like page numbers (e.g. {6}), \
metadata markers, or any text that should not be read aloud.

If you discover a new character not yet in the list, add them to \
"new_characters".

Return ONLY a JSON object in this exact format:
{
  "segments": [
    {"type": "dialogue", "text": "I'm a what?", "speaker": "harry_potter", "emotion": "fearful", "voice_stability": 0.35, "voice_style": 0.40, "voice_speed": 1.0, "sound_effect_description": null},
    {"type": "narration", "text": "gasped Harry.", "emotion": "neutral", "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0, "sound_effect_description": null},
    {"type": "dialogue", "text": "A wizard, o' course,", "speaker": "hagrid", "emotion": "excited", "voice_stability": 0.35, "voice_style": 0.40, "voice_speed": 1.0, "sound_effect_description": null}
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
- Reuse existing character_id values from the list above for known characters
- Only add to new_characters for genuinely new speakers not already listed
- For each new character, infer "sex" ("male", "female", or null if unknown) \
and "age" ("young", "adult", "elderly", or null if unknown) from context
- **New characters:** For each new character, add a "description": 1–2 sentences \
describing their voice and manner of speaking — include vocal quality (pitch, \
roughness, warmth), accent if evident, and personality as expressed in speech. \
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

    def _parse_response(
        self, response: str
    ) -> tuple[list[Segment], list[Character], list[tuple[str, str]], Optional[Scene]]:
        """Parse the AI response into Segment objects, new characters, description updates, and scene.

        Accepts two response shapes for backward compatibility:
        1. A JSON array (legacy) — treated as segments only, no new characters.
        2. A JSON object with ``"segments"``, ``"new_characters"``, and
           optionally ``"character_description_updates"`` and ``"scene"`` keys.

        Args:
            response: The JSON response from the AI

        Returns:
            Tuple of (segments, new_characters, description_updates, scene) where
            description_updates is a list of (character_id, description) pairs
            and scene is an optional :class:`Scene` if the AI detected one.

        Raises:
            ValueError: If the response cannot be parsed
        """
        try:
            # Clean response - sometimes LLMs add markdown code blocks
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as first_err:
                if "Extra data" not in str(first_err):
                    # Try to repair the JSON before giving up
                    try:
                        repaired = _repair_json(cleaned)
                        data = json.loads(repaired)
                    except json.JSONDecodeError:
                        raise first_err
                else:
                    # Model appended trailing text or returned multiple JSON objects.
                    # Extract and merge all valid JSON objects; ignore trailing garbage.
                    decoder = json.JSONDecoder()
                    merged: dict = {"segments": [], "new_characters": [], "character_description_updates": []}
                    pos = 0
                    found = 0
                    while pos < len(cleaned):
                        # Skip whitespace between objects
                        while pos < len(cleaned) and cleaned[pos] in " \t\n\r":
                            pos += 1
                        if pos >= len(cleaned):
                            break
                        try:
                            obj, end = decoder.raw_decode(cleaned, pos)
                        except json.JSONDecodeError:
                            break  # Trailing non-JSON content — stop here
                        found += 1
                        if isinstance(obj, dict):
                            merged["segments"].extend(obj.get("segments", []))
                            merged["new_characters"].extend(obj.get("new_characters", []))
                            merged["character_description_updates"].extend(
                                obj.get("character_description_updates", [])
                            )
                        elif isinstance(obj, list):
                            merged["segments"].extend(obj)
                        pos = end
                    if found == 0:
                        # Try to repair the JSON before giving up
                        try:
                            repaired = _repair_json(cleaned)
                            data = json.loads(repaired)
                        except json.JSONDecodeError:
                            raise first_err
                    else:
                        data = merged

            # Determine response shape
            if isinstance(data, dict):
                # New format: {"segments": [...], "new_characters": [...], "character_description_updates": [...]}
                segments_data = data.get("segments", [])
                new_chars_data = data.get("new_characters", [])
                desc_updates_data = data.get("character_description_updates", [])
            elif isinstance(data, list):
                # Legacy format: plain array of segments
                segments_data = data
                new_chars_data = []
                desc_updates_data = []
            else:
                raise ValueError("Response must be a JSON array")

            segments = []
            for item in segments_data:
                segment_type_str = item.get("type", "").lower()
                text = item.get("text", "")
                speaker = item.get("speaker")
                emotion_str: Optional[str] = item.get("emotion")

                # Map string type to SegmentType enum
                if segment_type_str == "dialogue":
                    segment_type = SegmentType.DIALOGUE
                elif segment_type_str == "narration":
                    segment_type = SegmentType.NARRATION
                elif segment_type_str == "illustration":
                    segment_type = SegmentType.ILLUSTRATION
                elif segment_type_str == "copyright":
                    segment_type = SegmentType.COPYRIGHT
                elif segment_type_str == "other":
                    segment_type = SegmentType.OTHER
                else:
                    # Default to narration for unknown types
                    segment_type = SegmentType.NARRATION

                # Narration segments always belong to the narrator character.
                # This fixes the "null narrator" bug: narration segments with
                # speaker=null are assigned the reserved "narrator" id.
                if segment_type == SegmentType.NARRATION and speaker is None:
                    character_id: Optional[str] = "narrator"
                else:
                    character_id = speaker

                # Store the emotion string as-is (freeform; validated at TTS time)
                emotion: Optional[str] = emotion_str if emotion_str else None

                # Voice settings from LLM (US-019 Fix 3): optional floats
                voice_stability: Optional[float] = item.get("voice_stability")
                voice_style: Optional[float] = item.get("voice_style")
                voice_speed: Optional[float] = item.get("voice_speed")

                # Sound effect description (US-023): optional string, only from explicit narrative mentions
                sound_effect_description: Optional[str] = item.get("sound_effect_description")

                segments.append(Segment(
                    text=text,
                    segment_type=segment_type,
                    character_id=character_id,
                    emotion=emotion,
                    voice_stability=voice_stability,
                    voice_style=voice_style,
                    voice_speed=voice_speed,
                    sound_effect_description=sound_effect_description,
                ))

            # Parse new characters
            new_characters: list[Character] = []
            for char_data in new_chars_data:
                cid = char_data.get("character_id")
                name = char_data.get("name", "")
                description = char_data.get("description")
                sex = char_data.get("sex")
                age = char_data.get("age")
                if cid:
                    new_characters.append(Character(
                        character_id=cid,
                        name=name,
                        description=description,
                        sex=sex,
                        age=age,
                    ))

            # Parse character description updates: list of (character_id, description) pairs
            description_updates: list[tuple[str, str]] = []
            for update in desc_updates_data:
                cid_update = update.get("character_id")
                new_desc = update.get("description")
                if cid_update and new_desc:
                    description_updates.append((cid_update, new_desc))

            # Parse scene (US-020) — optional, only present in dict-format responses.
            detected_scene: Optional[Scene] = None
            if isinstance(data, dict) and "scene" in data and data["scene"] is not None:
                scene_data = data["scene"]
                env = scene_data.get("environment", "unknown")
                hints = scene_data.get("acoustic_hints", [])
                voice_mods: dict[str, float] = {
                    k: float(v)
                    for k, v in scene_data.get("voice_modifiers", {}).items()
                }
                raw_ambient_prompt = scene_data.get("ambient_prompt")
                raw_ambient_volume = scene_data.get("ambient_volume")
                detected_scene = Scene(
                    scene_id=f"scene_{env}",
                    environment=env,
                    acoustic_hints=hints,
                    voice_modifiers=voice_mods,
                    ambient_prompt=str(raw_ambient_prompt) if raw_ambient_prompt is not None else None,
                    ambient_volume=float(raw_ambient_volume) if raw_ambient_volume is not None else None,
                )

            return segments, new_characters, description_updates, detected_scene

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid segment structure in response: {e}")
