"""Abstract interface for a character voice provider."""
from abc import ABC, abstractmethod

from src.domain.character import Character
from src.domain.models import Book


class CharacterProvider(ABC):
    """Owns the lifecycle of voices for the characters in a book."""

    @abstractmethod
    def upsert(self, character: Character) -> str:
        """Ensure *character* has a voice on the vendor and return the token."""

    @abstractmethod
    def get_all(self, book: Book) -> dict[str, str]:
        """Return the ``character_id -> voice_token`` map for *book*."""
