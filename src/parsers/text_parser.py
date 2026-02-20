"""Text book parser implementation."""
import re
from typing import Optional
from src.domain.models import Book, Chapter, Segment, SegmentType
from src.parsers.book_parser import BookParser


class TextBookParser(BookParser):
    """Parser for plain text books."""

    # Common attribution patterns
    # Pattern 1: "said Mr. Smith" or "said John" - with optional title
    # Pattern 2: "Mr. Smith said" or "John said" - speaker before verb
    # Pattern 3: "said his lady" - possessive descriptions
    ATTRIBUTION_PATTERNS = [
        # After dialogue: "said Mr. Smith" (with optional "to ...")
        r'(?:said|replied|cried|asked|exclaimed|whispered|shouted|answered|returned|continued)\s+((?:Mr\.|Mrs\.|Miss|Ms\.|Dr\.|Sir|Lady)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?:\s+to\s)',
        # After dialogue: "said Mr. Smith" or "said John"
        r'(?:said|replied|cried|asked|exclaimed|whispered|shouted|answered|returned|continued)\s+((?:Mr\.|Mrs\.|Miss|Ms\.|Dr\.|Sir|Lady)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)[,;.]',
        # Before dialogue: "Mr. Smith said" or "John said"
        r'((?:Mr\.|Mrs\.|Miss|Ms\.|Dr\.|Sir|Lady)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|replied|cried|asked|exclaimed|whispered|shouted|answered|returned|continued)',
        # Possessive: "said his lady"
        r'(?:said|replied|cried|asked|exclaimed|whispered|shouted|answered|returned|continued)\s+(his|her)\s+([a-z]+)',
    ]

    def __init__(self):
        self.attribution_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.ATTRIBUTION_PATTERNS]

    def parse(self, file_path: str) -> Book:
        """Parse a plain text book file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract metadata
        title = self._extract_title(content)
        author = self._extract_author(content)

        # Find the actual content start
        content_start = self._find_content_start(content)
        content = content[content_start:]

        # Parse chapters
        chapters = self._parse_chapters(content)

        return Book(title=title, author=author, chapters=chapters)

    def _extract_title(self, content: str) -> str:
        """Extract book title from content."""
        title_match = re.search(r'Title:\s*(.+)', content)
        if title_match:
            return title_match.group(1).strip()
        return "Unknown"

    def _extract_author(self, content: str) -> Optional[str]:
        """Extract author from content."""
        author_match = re.search(r'Author:\s*(.+)', content)
        if author_match:
            return author_match.group(1).strip()
        return None

    def _find_content_start(self, content: str) -> int:
        """Find where the actual book content starts."""
        # Look for common markers
        markers = [
            r'\*\*\* START OF .*? \*\*\*',
            r'Chapter I\.?[\]\s]',
            r'CHAPTER I\.?[\]\s]',
        ]

        for marker in markers:
            match = re.search(marker, content, re.IGNORECASE)
            if match:
                return match.start()

        return 0

    def _parse_chapters(self, content: str) -> list[Chapter]:
        """Parse chapters from content."""
        # Find chapter boundaries
        # Match both "Chapter I.]" (with bracket) and "Chapter I." (at end of line)
        # This handles various book formatting styles
        chapter_pattern = re.compile(
            r'^Chapter\s+([IVXLCDM]+|\d+)\.[\]\s]*$',
            re.IGNORECASE | re.MULTILINE
        )
        chapter_matches = list(chapter_pattern.finditer(content))

        if not chapter_matches:
            # Treat the whole content as one chapter
            return [self._parse_chapter_content(content, 1, "Chapter I")]

        chapters = []
        for i, match in enumerate(chapter_matches):
            chapter_num = self._roman_to_int(match.group(1))
            chapter_title = f"Chapter {match.group(1)}"

            # Get chapter content
            start_pos = match.end()
            end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(content)
            chapter_content = content[start_pos:end_pos]

            chapter = self._parse_chapter_content(chapter_content, chapter_num, chapter_title)
            chapters.append(chapter)

        return chapters

    def _parse_chapter_content(self, content: str, chapter_num: int, title: str) -> Chapter:
        """Parse a single chapter's content into segments."""
        segments = []

        # Split content into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        for paragraph in paragraphs:
            # Skip illustration markers and other non-content
            if paragraph.startswith('[Illustration') or paragraph.startswith('_Copyright'):
                continue

            segments.extend(self._parse_paragraph(paragraph))

        return Chapter(number=chapter_num, title=title, segments=segments)

    def _parse_paragraph(self, paragraph: str) -> list[Segment]:
        """Parse a paragraph into dialogue and narration segments."""
        segments = []
        current_pos = 0

        # Find all dialogue in the paragraph (supports both ASCII and Unicode quotes)
        # \u201c = " (left double quotation mark), \u201d = " (right double quotation mark)
        dialogue_pattern = re.compile(r'["\u201c]([^"\u201c\u201d]+)["\u201d]')

        for match in dialogue_pattern.finditer(paragraph):
            # Add narration before the dialogue
            if match.start() > current_pos:
                narration = paragraph[current_pos:match.start()].strip()
                if narration:
                    segments.append(Segment(
                        text=narration,
                        segment_type=SegmentType.NARRATION
                    ))

            # Add the dialogue
            dialogue_text = match.group(1)
            speaker, attribution_end = self._extract_speaker(paragraph, match.start(), match.end())

            segments.append(Segment(
                text=dialogue_text,
                segment_type=SegmentType.DIALOGUE,
                speaker=speaker
            ))

            # Skip the attribution text if we found one
            if attribution_end > match.end():
                current_pos = attribution_end
            else:
                current_pos = match.end()

        # Add remaining narration
        if current_pos < len(paragraph):
            narration = paragraph[current_pos:].strip()
            if narration:
                segments.append(Segment(
                    text=narration,
                    segment_type=SegmentType.NARRATION
                ))

        # If no dialogue found, treat whole paragraph as narration
        if not segments:
            segments.append(Segment(
                text=paragraph,
                segment_type=SegmentType.NARRATION
            ))

        return segments

    def _extract_speaker(self, paragraph: str, dialogue_start: int, dialogue_end: int) -> tuple[Optional[str], int]:
        """
        Extract the speaker from attribution around the dialogue.

        Returns:
            tuple: (speaker_name, end_position_of_attribution)
        """
        # Look for attribution after the dialogue (within next 100 chars)
        after_text = paragraph[dialogue_end:dialogue_end + 100]

        for regex in self.attribution_regex:
            match = regex.search(after_text)
            if match:
                # Handle multiple capture groups (e.g., "his lady" has 2 groups)
                speaker = match.group(match.lastindex).strip() if match.lastindex else match.group(1).strip()
                # Return speaker and the position after the attribution
                attribution_end = dialogue_end + match.end()
                return self._normalize_speaker_name(speaker), attribution_end

        # Look for attribution before the dialogue (within previous 100 chars)
        before_start = max(0, dialogue_start - 100)
        before_text = paragraph[before_start:dialogue_start]

        for regex in self.attribution_regex:
            match = regex.search(before_text)
            if match:
                # Handle multiple capture groups
                speaker = match.group(match.lastindex).strip() if match.lastindex else match.group(1).strip()
                # Attribution is before, so return the dialogue end position
                return self._normalize_speaker_name(speaker), dialogue_end

        return None, dialogue_end

    def _normalize_speaker_name(self, speaker: str) -> str:
        """Normalize speaker name (remove titles, possessives, etc)."""
        # Remove common prefixes - note we need to match after removal
        normalized = re.sub(r'^(Mr\.|Mrs\.|Miss|Ms\.|Dr\.|Sir|Lady)\s+', '', speaker, flags=re.IGNORECASE).strip()

        # If nothing left after removal, return original
        if not normalized:
            return speaker.strip()

        # Take only the last name if there are multiple words
        parts = normalized.split()
        if len(parts) > 1:
            # Handle cases like "his lady" -> "Mrs. Bennet" contextually
            # For now, just take the last word
            return parts[-1].strip()

        return normalized

    def _roman_to_int(self, roman: str) -> int:
        """Convert Roman numeral to integer."""
        if roman.isdigit():
            return int(roman)

        roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
        roman = roman.upper()
        result = 0
        prev_value = 0

        for char in reversed(roman):
            value = roman_map.get(char, 0)
            if value < prev_value:
                result -= value
            else:
                result += value
            prev_value = value

        return result
