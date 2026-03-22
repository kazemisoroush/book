"""AI-powered section parser that segments text into dialogue and narration."""
import json
import time
from typing import Optional
from src.ai.ai_provider import AIProvider
from src.parsers.book_section_parser import BookSectionParser
from src.domain.models import Section, Segment, SegmentType

_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class AISectionParser(BookSectionParser):
    """Uses AI to intelligently segment sections into dialogue and narration.

    This parser leverages LLMs to:
    - Identify dialogue vs narration
    - Determine speakers for dialogue segments
    - Handle complex cases like interrupted dialogue and nested quotes

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

    def parse(self, section: Section) -> list[Segment]:
        """Parse a section into segments using AI.

        Retries up to _MAX_RETRIES times on empty or unparseable responses
        before raising.

        Args:
            section: The section to parse

        Returns:
            List of segments (dialogue and narration)

        Raises:
            ValueError: If the AI response cannot be parsed after all retries
            Exception: If the AI provider fails
        """
        prompt = self._build_prompt(section.text)
        last_error: Exception = ValueError("No attempts made")
        for attempt in range(_MAX_RETRIES):
            response = self.ai_provider.generate(prompt, max_tokens=2000)
            if not response.strip():
                last_error = ValueError("Empty response from AI provider")
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
                continue
            try:
                return self._parse_response(response)
            except ValueError as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
        raise last_error

    def _build_prompt(self, text: str) -> str:
        """Build the prompt for the AI model.

        Args:
            text: The section text to segment

        Returns:
            The formatted prompt
        """
        context = ""
        if self.book_title and self.book_author:
            context = (
                f"\n\nBook context: '{self.book_title}' "
                f"by {self.book_author}"
            )
        elif self.book_title:
            context = f"\n\nBook context: '{self.book_title}'"

        return f"""Break down the following text into segments \
alternating between narration and dialogue.

For each segment, identify:
- type: "dialogue", "narration", "illustration", or "copyright"
- text: the actual text content (without quotes for dialogue)
- speaker: the character name for dialogue (optional, use null if unknown)

Return ONLY a JSON array in this exact format:
[
  {{"type": "dialogue", "text": "I'm a what?", \
"speaker": "Harry Potter"}},
  {{"type": "narration", "text": "gasped Harry."}},
  {{"type": "dialogue", "text": "A wizard, o' course,", \
"speaker": "Hagrid"}}
]

Rules:
- Strip quotation marks from dialogue text
- Keep narration text exactly as written
- Identify speakers by name when possible
- Return valid JSON only, no other text{context}

Text to segment:
{text}"""

    def _parse_response(self, response: str) -> list[Segment]:
        """Parse the AI response into Segment objects.

        Args:
            response: The JSON response from the AI

        Returns:
            List of Segment objects

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

            if not isinstance(data, list):
                raise ValueError("Response must be a JSON array")

            segments = []
            for item in data:
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

                segments.append(Segment(
                    text=text,
                    segment_type=segment_type,
                    speaker=speaker
                ))

            return segments

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid segment structure in response: {e}")
