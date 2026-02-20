"""Core domain models for the audiobook pipeline."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SegmentType(Enum):
    """Type of text segment."""
    NARRATION = "narration"
    DIALOGUE = "dialogue"


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


@dataclass
class Chapter:
    """A chapter containing multiple segments."""
    number: int
    title: str
    segments: list[Segment]


@dataclass
class Book:
    """A book containing multiple chapters."""
    title: str
    author: Optional[str]
    chapters: list[Chapter]
