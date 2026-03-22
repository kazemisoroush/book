"""Core domain models for the audiobook pipeline."""
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional


class SegmentType(Enum):
    """Type of text segment."""
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    ILLUSTRATION = "illustration"
    COPYRIGHT = "copyright"


@dataclass
class EmphasisSpan:
    """A span of emphasised text within a Section.

    Character offsets refer to the plain-text ``text`` field of the
    containing Section.  ``start`` is inclusive, ``end`` is exclusive
    — matching Python slice semantics.

    ``kind`` records which HTML inline element (or equivalent markup)
    produced the emphasis: one of ``"em"``, ``"b"``, ``"strong"``,
    ``"i"``.  This is a universal abstraction — the HTML adapter is
    merely one producer; future EPUB or plain-text producers may
    populate the same field.
    """
    start: int
    end: int
    kind: str


@dataclass
class Segment:
    """A single piece of text (narration or dialogue)."""
    text: str
    segment_type: SegmentType
    speaker: Optional[str] = None  # Character name for dialogue

    def is_dialogue(self) -> bool:
        return self.segment_type == SegmentType.DIALOGUE

    def is_narration(self) -> bool:
        return self.segment_type == SegmentType.NARRATION

    def is_illustration(self) -> bool:
        return self.segment_type == SegmentType.ILLUSTRATION

    def is_copyright(self) -> bool:
        return self.segment_type == SegmentType.COPYRIGHT


@dataclass
class Section:
    """A section (paragraph) of text, optionally segmented.

    A section represents a paragraph. Simple narration paragraphs
    have just text. Paragraphs with dialogue are broken down into
    segments (dialogue/narration).

    ``emphases`` records inline emphasis spans (from ``<em>``, ``<b>``,
    ``<strong>``, ``<i>`` in HTML sources, or equivalent in other
    formats).  Character offsets are relative to ``text``.
    """
    text: str
    segments: Optional[list[Segment]] = None
    emphases: list[EmphasisSpan] = field(default_factory=list)


@dataclass
class Chapter:
    """A chapter containing multiple sections (paragraphs)."""
    number: int
    title: str
    sections: list[Section]


@dataclass
class BookMetadata:
    """Book metadata containing bibliographic information."""
    title: str
    author: Optional[str]
    releaseDate: Optional[str]
    language: Optional[str]
    originalPublication: Optional[str]
    credits: Optional[str]


@dataclass
class BookContent:
    """Book content containing chapters and sections."""
    chapters: list[Chapter]


@dataclass
class Book:
    """Complete book with metadata and content."""
    metadata: BookMetadata
    content: BookContent

    def to_dict(self) -> dict:
        """Convert Book to JSON-serializable dictionary.

        Recursively converts all dataclasses and enums to dictionaries
        and strings respectively.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        def convert_value(obj):  # type: ignore[no-untyped-def]
            """Recursively convert objects to JSON-serializable types."""
            if isinstance(obj, SegmentType):
                return obj.value
            elif hasattr(obj, '__dataclass_fields__'):
                return asdict(obj)
            elif isinstance(obj, list):
                return [convert_value(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_value(val) for key, val in obj.items()}
            else:
                return obj

        return convert_value(asdict(self))
