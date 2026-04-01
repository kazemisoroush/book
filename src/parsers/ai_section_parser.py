"""AI-powered section parser that segments text into dialogue and narration."""
import json
import time
from dataclasses import replace as dc_replace
from typing import Optional
import structlog
from src.ai.ai_provider import AIProvider
from src.parsers.book_section_parser import BookSectionParser
from src.domain.models import (
    Section, Segment, SegmentType, CharacterRegistry, Character,
)

_MAX_RETRIES = 3
_RETRY_DELAY = 1.0

logger = structlog.get_logger(__name__)


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

    def parse(
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
    ) -> tuple[list[Segment], CharacterRegistry]:
        """Parse a section into segments using AI.

        Includes the current registry in the prompt so the AI can reuse
        existing character IDs and emit new ones.  Any new characters
        returned by the AI are upserted into the registry before returning.

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

        Returns:
            Tuple of (segments, updated_registry).

        Raises:
            ValueError: If the AI response cannot be parsed after all retries
            Exception: If the AI provider fails
        """
        # Short-circuit: sections with a pre-resolved type skip the LLM call.
        if section.section_type is not None:
            valid_values = {t.value for t in SegmentType}
            seg_type = (
                SegmentType(section.section_type)
                if section.section_type in valid_values
                else SegmentType.OTHER
            )
            return [Segment(text=section.text, segment_type=seg_type)], registry

        # Short-circuit: empty text sections skip the LLM call entirely.
        if not section.text.strip():
            return [], registry

        prompt = self._build_prompt(section.text, registry, context_window)
        last_error: Exception = ValueError("No attempts made")
        text_preview = section.text[:60].replace("\n", " ")
        for attempt in range(_MAX_RETRIES):
            response = self.ai_provider.generate(prompt, max_tokens=2000)
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
                segments, new_characters, description_updates = self._parse_response(response)
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
    ) -> str:
        """Build the prompt for the AI model.

        Includes the current character registry so the AI can reuse IDs for
        known characters and emit new entries for genuinely new ones.

        When ``context_window`` is non-empty, a read-only surrounding-context
        block is prepended so the AI can resolve pronouns and infer turn-taking
        across section boundaries.

        Args:
            text: The section text to segment.
            registry: Current character registry for context.
            context_window: Optional neighbouring sections for speaker inference
                            (read-only — the AI must not re-segment them).

        Returns:
            The formatted prompt.
        """
        book_context = ""
        if self.book_title and self.book_author:
            book_context = (
                f"\n\nBook context: '{self.book_title}' "
                f"by {self.book_author}"
            )
        elif self.book_title:
            book_context = f"\n\nBook context: '{self.book_title}'"

        # Build registry context block (include description when present)
        registry_lines = []
        for char in registry.characters:
            line = f'  - character_id: "{char.character_id}", name: "{char.name}"'
            if char.description:
                line += f', description: "{char.description}"'
            registry_lines.append(line)
        registry_context = "\n".join(registry_lines) if registry_lines else "  (empty)"

        # Build surrounding context block
        surrounding_context_block = ""
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
            surrounding_context_block = f"""
## Surrounding context (for speaker inference only — do not segment)
The following sections appear immediately before the target text.
Use them for context only to resolve speakers, pronouns, and turn-taking.
If you can identify the speaker of a dialogue from this context, do so:
add them to new_characters if they are not already in the character list above.

{ctx_texts}

---
"""

        return f"""Break down the following text into segments \
alternating between narration and dialogue.

## Existing characters (reuse these IDs — do NOT create duplicates)
{registry_context}
{surrounding_context_block}
For each segment, identify:
- type: "dialogue", "narration", "illustration", "copyright", or "other"
- text: the actual text content (without quotes for dialogue)
- speaker: the character_id for dialogue (use existing IDs from the list \
above when possible; use null if unknown)
- emotion: an audio tag describing the vocal delivery at this moment. \
Must be auditory — a vocal quality, sound, or delivery style \
(e.g. whispers, sighs, laughs, sarcastic, excited, crying, laughs harder, \
curious, mischievously). Do NOT use visual actions (grinning, standing, \
pacing). Use "neutral" for narration and for dialogue with no discernible \
emotional charge. If the emotional tone shifts significantly mid-utterance, \
split the utterance into multiple segments each with its own emotion value.

Use "other" for non-narratable content like page numbers (e.g. {6}), \
metadata markers, or any text that should not be read aloud.

If you discover a new character not yet in the list, add them to \
"new_characters".

Return ONLY a JSON object in this exact format:
{{
  "segments": [
    {{"type": "dialogue", "text": "I'm a what?", "speaker": "harry_potter", "emotion": "fearful"}},
    {{"type": "narration", "text": "gasped Harry.", "emotion": "neutral"}},
    {{"type": "dialogue", "text": "A wizard, o' course,", "speaker": "hagrid", "emotion": "excited"}}
  ],
  "new_characters": [
    {{"character_id": "hagrid", "name": "Rubeus Hagrid", "sex": "male", "age": "adult", \
"description": "booming bass voice, thick West Country accent, warm and boisterous"}}
  ],
  "character_description_updates": [
    {{"character_id": "hagrid", \
"description": "booming bass voice, thick West Country accent; voice trembles when distressed"}}
  ]
}}

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
- Return valid JSON only, no other text{book_context}

Text to segment:
{text}"""

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
    ) -> tuple[list[Segment], list[Character], list[tuple[str, str]]]:
        """Parse the AI response into Segment objects, new characters, and description updates.

        Accepts two response shapes for backward compatibility:
        1. A JSON array (legacy) — treated as segments only, no new characters.
        2. A JSON object with ``"segments"``, ``"new_characters"``, and
           optionally ``"character_description_updates"`` keys.

        Args:
            response: The JSON response from the AI

        Returns:
            Tuple of (segments, new_characters, description_updates) where
            description_updates is a list of (character_id, description) pairs.

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
                    raise
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
                    raise first_err
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

                segments.append(Segment(
                    text=text,
                    segment_type=segment_type,
                    character_id=character_id,
                    emotion=emotion,
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

            return segments, new_characters, description_updates

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid segment structure in response: {e}")
