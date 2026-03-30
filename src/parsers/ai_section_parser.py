"""AI-powered section parser that segments text into dialogue and narration."""
import json
import time
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
    - Emit new character entries for previously-unseen characters
    - Handle complex cases like interrupted dialogue and nested quotes

    The registry is threaded through each call so that character IDs remain
    consistent across the full book.

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
        book_author: Optional[str] = None
    ):
        """Initialize the AI section parser.

        Args:
            ai_provider: The AI provider to use for segmentation
            book_title: Optional book title for context
            book_author: Optional book author for context
        """
        self.ai_provider = ai_provider
        self.book_title = book_title
        self.book_author = book_author

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
                            the 3 preceding sections) provided as read-only
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
                segments, new_characters = self._parse_response(response)
                for char in new_characters:
                    registry.upsert(char)
                logger.debug(
                    "ai_section_parsed",
                    segment_count=len(segments),
                    new_character_count=len(new_characters),
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

        # Build registry context block
        registry_lines = []
        for char in registry.characters:
            registry_lines.append(f'  - character_id: "{char.character_id}", name: "{char.name}"')
        registry_context = "\n".join(registry_lines) if registry_lines else "  (empty)"

        # Build surrounding context block
        surrounding_context_block = ""
        if context_window:
            ctx_texts = "\n\n---\n\n".join(s.text for s in context_window)
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
    {{"character_id": "hagrid", "name": "Rubeus Hagrid", "sex": "male", "age": "adult"}}
  ]
}}

Rules:
- Strip quotation marks from dialogue text
- Keep narration text exactly as written
- Reuse existing character_id values from the list above for known characters
- Only add to new_characters for genuinely new speakers not already listed
- For each new character, infer "sex" ("male", "female", or null if unknown) \
and "age" ("young", "adult", "elderly", or null if unknown) from context
- If context window sections identify a speaker, use that — infer from \
turn-taking, pronouns, and names mentioned in adjacent sections
- Return valid JSON only, no other text{book_context}

Text to segment:
{text}"""

    def _parse_response(
        self, response: str
    ) -> tuple[list[Segment], list[Character]]:
        """Parse the AI response into Segment objects and new characters.

        Accepts two response shapes for backward compatibility:
        1. A JSON array (legacy) — treated as segments only, no new characters.
        2. A JSON object with ``"segments"`` and ``"new_characters"`` keys.

        Args:
            response: The JSON response from the AI

        Returns:
            Tuple of (segments, new_characters)

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
                merged: dict = {"segments": [], "new_characters": []}
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
                    elif isinstance(obj, list):
                        merged["segments"].extend(obj)
                    pos = end
                if found == 0:
                    raise first_err
                data = merged

            # Determine response shape
            if isinstance(data, dict):
                # New format: {"segments": [...], "new_characters": [...]}
                segments_data = data.get("segments", [])
                new_chars_data = data.get("new_characters", [])
            elif isinstance(data, list):
                # Legacy format: plain array of segments
                segments_data = data
                new_chars_data = []
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

            return segments, new_characters

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid segment structure in response: {e}")
