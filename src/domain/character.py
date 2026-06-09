"""Character domain model and narrator factory."""
from dataclasses import dataclass
from typing import Optional

from src.domain.character_id import build_character_id

NARRATOR_NAME = "Narrator"
_NARRATOR_DESCRIPTION = "calm, warm voice with a neutral accent and steady pacing"


@dataclass
class Character:
    """A voice character in the audiobook."""

    character_id: str
    name: str
    description: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[str] = None
    voice_id: Optional[str] = None

    @property
    def voice_design_prompt(self) -> Optional[str]:
        """Return the voice-design prompt for this character, or None if no description."""
        if not self.description:
            return None
        desc = self.description.rstrip(".")
        segments = []
        if self.age:
            segments.append(f"Age: {self.age}.")
        if self.sex:
            segments.append(f"Sex: {self.sex}.")
        segments.append(f"Description: {desc}.")
        return " ".join(segments)

    def set_voice_id(self, voice_id: str) -> None:
        """Stamp *voice_id* on this character in place."""
        self.voice_id = voice_id

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "character_id": self.character_id,
            "name": self.name,
            "description": self.description,
            "sex": self.sex,
            "age": self.age,
            "voice_id": self.voice_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":  # type: ignore[type-arg]
        """Construct a Character from a dictionary produced by :meth:`to_dict`."""
        return cls(
            character_id=data["character_id"],
            name=data["name"],
            description=data.get("description"),
            sex=data.get("sex"),
            age=data.get("age"),
            voice_id=data.get("voice_id"),
        )


def make_default_narrator(book_id: str) -> Character:
    """Return the default narrator :class:`Character` for *book_id*."""
    return Character(
        character_id=build_character_id(book_id, NARRATOR_NAME),
        name=NARRATOR_NAME,
        description=_NARRATOR_DESCRIPTION,
    )
