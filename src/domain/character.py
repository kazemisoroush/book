"""Character domain model and narrator factory."""
from dataclasses import dataclass
from typing import Optional

NARRATOR_NAME = "Narrator"
NARRATOR_ID = 1


@dataclass
class Character:
    """A voice character in the audiobook."""

    id: int
    name: str
    gender: Optional[str] = None
    age: Optional[str] = None
    accent: Optional[str] = None

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "age": self.age,
            "accent": self.accent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":  # type: ignore[type-arg]
        """Construct a Character; reads ``gender`` falling back to legacy ``sex``."""
        return cls(
            id=data["id"],
            name=data["name"],
            gender=data.get("gender", data.get("sex")),
            age=data.get("age"),
            accent=data.get("accent"),
        )


def make_default_narrator() -> Character:
    """Return the default narrator :class:`Character` (id=1)."""
    return Character(
        id=NARRATOR_ID,
        name=NARRATOR_NAME,
        gender="male",
        age="middle_aged",
    )
