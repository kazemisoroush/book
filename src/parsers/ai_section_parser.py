"""AI-powered section parser that segments text into dialogue and narration."""
import json
import time
from typing import Optional
from src.ai.ai_provider import AIProvider
from src.parsers.book_section_parser import BookSectionParser
from src.domain.models import (
    Section, Segment, SegmentType, CharacterRegistry, Character,
)

_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class AISectionParser(BookSectionParser):
    """Uses AI to intelligently segment sections into dialogue and narration.

    This parser leverages LLMs to:
    - Identify dialogue vs narration
    - Determine speakers for dialogue segments, using existing registry IDs
    - Emit new character entries for previously-unseen characters
    - Handle complex cases like interrupted dialogue and nested quotes

    The registry is threaded through each call so that character IDs remain
    consistent across the full book.

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

        Returns:
            Tuple of (segments, updated_registry).

        Raises:
            ValueError: If the AI response cannot be parsed after all retries
            Exception: If the AI provider fails
        """
        prompt = self._build_prompt(section.text, registry)
        last_error: Exception = ValueError("No attempts made")
        for attempt in range(_MAX_RETRIES):
            response = self.ai_provider.generate(prompt, max_tokens=2000)
            if not response.strip():
                last_error = ValueError("Empty response from AI provider")
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
                continue
            try:
                segments, new_characters = self._parse_response(response)
                for char in new_characters:
                    registry.upsert(char)
                return segments, registry
            except ValueError as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
        raise last_error

    def _build_prompt(self, text: str, registry: CharacterRegistry) -> str:
        """Build the prompt for the AI model.

        Includes the current character registry so the AI can reuse IDs for
        known characters and emit new entries for genuinely new ones.

        Args:
            text: The section text to segment.
            registry: Current character registry for context.

        Returns:
            The formatted prompt.
        """
        context = ""
        if self.book_title and self.book_author:
            context = (
                f"\n\nBook context: '{self.book_title}' "
                f"by {self.book_author}"
            )
        elif self.book_title:
            context = f"\n\nBook context: '{self.book_title}'"

        # Build registry context block
        registry_lines = []
        for char in registry.characters:
            registry_lines.append(f'  - character_id: "{char.character_id}", name: "{char.name}"')
        registry_context = "\n".join(registry_lines) if registry_lines else "  (empty)"

        return f"""Break down the following text into segments \
alternating between narration and dialogue.

## Existing characters (reuse these IDs — do NOT create duplicates)
{registry_context}

For each segment, identify:
- type: "dialogue", "narration", "illustration", or "copyright"
- text: the actual text content (without quotes for dialogue)
- speaker: the character_id for dialogue (use existing IDs from the list \
above when possible; use null if unknown)

If you discover a new character not yet in the list, add them to \
"new_characters".

Return ONLY a JSON object in this exact format:
{{
  "segments": [
    {{"type": "dialogue", "text": "I'm a what?", "speaker": "harry_potter"}},
    {{"type": "narration", "text": "gasped Harry."}},
    {{"type": "dialogue", "text": "A wizard, o' course,", "speaker": "hagrid"}}
  ],
  "new_characters": [
    {{"character_id": "hagrid", "name": "Rubeus Hagrid"}}
  ]
}}

Rules:
- Strip quotation marks from dialogue text
- Keep narration text exactly as written
- Reuse existing character_id values from the list above for known characters
- Only add to new_characters for genuinely new speakers not already listed
- Return valid JSON only, no other text{context}

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

            data = json.loads(cleaned)

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

                # Map string type to SegmentType enum
                if segment_type_str == "dialogue":
                    segment_type = SegmentType.DIALOGUE
                elif segment_type_str == "narration":
                    segment_type = SegmentType.NARRATION
                elif segment_type_str == "illustration":
                    segment_type = SegmentType.ILLUSTRATION
                elif segment_type_str == "copyright":
                    segment_type = SegmentType.COPYRIGHT
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

                segments.append(Segment(
                    text=text,
                    segment_type=segment_type,
                    character_id=character_id
                ))

            # Parse new characters
            new_characters: list[Character] = []
            for char_data in new_chars_data:
                cid = char_data.get("character_id")
                name = char_data.get("name", "")
                description = char_data.get("description")
                if cid:
                    new_characters.append(Character(
                        character_id=cid,
                        name=name,
                        description=description,
                    ))

            return segments, new_characters

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid segment structure in response: {e}")
