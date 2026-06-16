"""Typed output payload returned by the chapter_parser prompt."""
from dataclasses import dataclass
from typing import Optional

from src.domain.voice_settings import VoiceSettings


@dataclass(frozen=True)
class PromptOutputBeat:
    """A single beat in the chapter_parser response."""
    id: int
    type: str
    text: str
    char_id: int
    sec_id: Optional[int] = None
    emotion: Optional[str] = None
    voice_settings: Optional[VoiceSettings] = None


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
    gender: Optional[str] = None
    age: Optional[str] = None
    accent: Optional[str] = None


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
                        char_id=b["char_id"],
                        sec_id=b.get("sec_id"),
                        emotion=b.get("emotion"),
                        voice_settings=(
                            VoiceSettings(**b["voice_settings"])
                            if b.get("voice_settings") is not None
                            else None
                        ),
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
                gender=c.get("gender", c.get("sex")),
                age=c.get("age"),
                accent=c.get("accent"),
            )
            for c in data.get("characters", [])
        ]
        return cls(chapters=chapters, characters=characters)
