"""Core domain models for the audiobook pipeline."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SegmentType(Enum):
    """Type of text segment."""
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    ILLUSTRATION = "illustration"
    COPYRIGHT = "copyright"


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
    """A section (paragraph) of text, optionally broken down into segments.

    A section represents a paragraph. Simple narration paragraphs have just text.
    Paragraphs with dialogue are broken down into segments (dialogue/narration).
    """
    text: str
    segments: Optional[list[Segment]] = None


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
