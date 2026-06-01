"""Typed output payload returned by the chapter_parser prompt."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PromptOutputBeat:
    """A single beat in the chapter_parser response."""
    id: int
    type: str
    text: str
    character_id: int
    emotion: Optional[str] = None


@dataclass(frozen=True)
class PromptOutputChapter:
    """A chapter section of the chapter_parser response."""
    id: int
    beats: list[PromptOutputBeat]


@dataclass(frozen=True)
class PromptOutputCharacter:
    """A character recognised by the chapter_parser prompt."""
    id: int
    name: str
    sex: Optional[str] = None
    age: Optional[str] = None


@dataclass(frozen=True)
class PromptOutput:
    """Full response payload from the chapter_parser prompt."""
    chapters: list[PromptOutputChapter]
    characters: list[PromptOutputCharacter]

    @classmethod
    def from_dict(cls, data: dict) -> "PromptOutput":
        """Parse a JSON-decoded chapter_parser response into a PromptOutput."""
        chapters = [
            PromptOutputChapter(
                id=ch["id"],
                beats=[
                    PromptOutputBeat(
                        id=b["id"],
                        type=b["type"],
                        text=b["text"],
                        character_id=b["character_id"],
                        emotion=b.get("emotion"),
                    )
                    for b in ch["beats"]
                ],
            )
            for ch in data["chapters"]
        ]
        characters = [
            PromptOutputCharacter(
                id=c["id"],
                name=c["name"],
                sex=c.get("sex"),
                age=c.get("age"),
            )
            for c in data.get("characters", [])
        ]
        return cls(chapters=chapters, characters=characters)
