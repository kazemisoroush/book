"""Character domain model and narrator factory."""
from dataclasses import dataclass, field
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
    descriptives: list[str] = field(default_factory=list)

    @property
    def description(self) -> str:
        """Derive a single-sentence voice description from the structured attributes."""
        parts: list[str] = []
        if self.age:
            parts.append(self.age.replace("_", " "))
        if self.accent:
            parts.append(self.accent)
        if self.gender:
            parts.append(self.gender.replace("_", " "))
        descriptor = " ".join(parts).strip() or "neutral"
        adjectives = ", ".join(self.descriptives).strip()
        if adjectives:
            return f"A {descriptor} voice that sounds {adjectives}."
        return f"A {descriptor} voice."

    @property
    def voice_design_prompt(self) -> str:
        """Return the voice-design prompt for this character."""
        return self.description

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "age": self.age,
            "accent": self.accent,
            "descriptives": list(self.descriptives),
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
            descriptives=list(data.get("descriptives") or []),
        )


def make_default_narrator() -> Character:
    """Return the default third-person narrator :class:`Character` (id=1)."""
    return Character(
        id=NARRATOR_ID,
        name=NARRATOR_NAME,
        gender="non_binary",
        age="middle_aged",
        descriptives=["warm", "calm"],
    )
