"""Abstract interface for a character voice provider."""
from abc import ABC, abstractmethod

from src.domain.character import Character


class CharacterProvider(ABC):
    """Owns the lifecycle of voices for the characters in a book."""

    @abstractmethod
    def upsert(self, character: Character, book_id: str) -> str:
        """Ensure *character* has a voice on the vendor and return the token."""
