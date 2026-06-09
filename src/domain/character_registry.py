"""CharacterRegistry domain model."""
from dataclasses import dataclass, field
from typing import Optional

from src.domain.character import Character


@dataclass
class CharacterRegistry:
    """Holds every :class:`Character` discovered while processing a book."""

    characters: list[Character] = field(default_factory=list)

    def get(self, character_id: int) -> Optional[Character]:
        """Return the character with ``id == character_id``, or None if absent."""
        for char in self.characters:
            if char.id == character_id:
                return char
        return None

    def add(self, character: Character) -> None:
        """Append a new character. Does not check for duplicates."""
        self.characters.append(character)

    def upsert(self, character: Character) -> None:
        """Add *character* if absent, or replace the existing entry if present."""
        for i, char in enumerate(self.characters):
            if char.id == character.id:
                self.characters[i] = character
                return
        self.characters.append(character)
