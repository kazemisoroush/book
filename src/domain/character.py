"""Character domain model and narrator factory."""
from dataclasses import dataclass
from typing import Optional

NARRATOR_NAME = "Narrator"
_NARRATOR_DESCRIPTION = "calm, warm voice with a neutral accent and steady pacing"
NARRATOR_ID = 1


@dataclass
class Character:
    """A voice character in the audiobook."""

    id: int
    name: str
    description: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[str] = None

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

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sex": self.sex,
            "age": self.age,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":  # type: ignore[type-arg]
        """Construct a Character from a dictionary produced by :meth:`to_dict`."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            sex=data.get("sex"),
            age=data.get("age"),
        )


def make_default_narrator() -> Character:
    """Return the default narrator :class:`Character` (id=1)."""
    return Character(
        id=NARRATOR_ID,
        name=NARRATOR_NAME,
        description=_NARRATOR_DESCRIPTION,
    )
