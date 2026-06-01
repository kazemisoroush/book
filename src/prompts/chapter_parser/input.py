"""Typed input payload for the chapter_parser prompt."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptInputMetadata:
    """Book metadata block sent to the chapter_parser prompt."""
    title: str
    author: str


@dataclass(frozen=True)
class PromptInputSection:
    """A single section of a chapter passed to the chapter_parser prompt."""
    id: int
    text: str
    type: str


@dataclass(frozen=True)
class PromptInputChapter:
    """A chapter passed to the chapter_parser prompt."""
    id: int
    sections: list[PromptInputSection]


@dataclass(frozen=True)
class PromptInputCharacter:
    """A pre-known character passed to the chapter_parser prompt."""
    id: int
    name: str
    sex: str
    age: str


@dataclass(frozen=True)
class PromptInput:
    """Full input payload for the chapter_parser prompt."""
    metadata: PromptInputMetadata
    chapters: list[PromptInputChapter]
    characters: list[PromptInputCharacter] = field(default_factory=list)
