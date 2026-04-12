"""AI-powered section parser that segments text into dialogue and narration."""
import json
import re
import time
from dataclasses import replace as dc_replace
from typing import Optional
import structlog
from src.ai.ai_provider import AIProvider
from src.parsers.book_section_parser import BookSectionParser
from src.parsers.prompt_builder import PromptBuilder
from src.parsers.text_sanitizer import sanitize_segment_text
from src.domain.models import (
    Section, Segment, SegmentType, CharacterRegistry, Character, Scene,
    SceneRegistry,
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

    # Replace literal newlines not inside strings with escaped versions
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
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        """Initialize the AI section parser.

        Args:
            ai_provider: The AI provider to use for segmentation
            prompt_builder: Optional PromptBuilder for prompt assembly.
                            If None, a default PromptBuilder with no book
                            context is created.
        """
        self.ai_provider = ai_provider
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.last_detected_scene: Optional[Scene] = None

    def parse(
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
        is_book_start: bool = False,
        is_chapter_start: bool = False,
        chapter_title: Optional[str] = None,
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
            seg_type = SegmentType.from_string(section.section_type, default=SegmentType.OTHER)
            return [Segment(text=section.text, segment_type=seg_type)], registry

        # Short-circuit: empty text sections skip the LLM call entirely.
        if not section.text.strip():
            self.last_detected_scene = None
            return [], registry

        prompt = self.prompt_builder.build_prompt(
            section.text, registry, context_window, scene_registry=scene_registry,
            is_book_start=is_book_start, is_chapter_start=is_chapter_start,
            chapter_title=chapter_title,
        )
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
                # Strip non-audio segments (illustration, copyright, other)
                # so the caller only receives audio-producible content (dialogue, narration, sound effects).
                segments = [
                    s for s in segments
                    if s.is_narratable or s.segment_type == SegmentType.SOUND_EFFECT
                    or s.segment_type == SegmentType.VOCAL_EFFECT
                ]
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
                text = sanitize_segment_text(item.get("text", ""))
                speaker = item.get("speaker")
                emotion_str: Optional[str] = item.get("emotion")

                # Map string type to SegmentType enum
                segment_type = SegmentType.from_string(segment_type_str)

                # Narration segments always belong to the narrator character.
                # This fixes the "null narrator" bug: narration segments with
                # speaker=null are assigned the reserved "narrator" id.
                # SOUND_EFFECT segments have no character_id (they are not spoken).
                if segment_type in {SegmentType.NARRATION, SegmentType.BOOK_TITLE} and speaker is None:
                    character_id: Optional[str] = "narrator"
                elif segment_type == SegmentType.SOUND_EFFECT:
                    character_id = None
                else:
                    character_id = speaker

                # Store the emotion string as-is (freeform; validated at TTS time)
                emotion: Optional[str] = emotion_str if emotion_str else None

                # Voice settings from LLM: optional floats
                voice_stability: Optional[float] = item.get("voice_stability")
                voice_style: Optional[float] = item.get("voice_style")
                voice_speed: Optional[float] = item.get("voice_speed")

                # Sound effect detail: optional string for SOUND_EFFECT segments
                sound_effect_detail: Optional[str] = item.get("sound_effect_detail")

                segments.append(Segment(
                    text=text,
                    segment_type=segment_type,
                    character_id=character_id,
                    emotion=emotion,
                    voice_stability=voice_stability,
                    voice_style=voice_style,
                    voice_speed=voice_speed,
                    sound_effect_detail=sound_effect_detail,
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

            # Parse scene — optional, only present in dict-format responses.
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
