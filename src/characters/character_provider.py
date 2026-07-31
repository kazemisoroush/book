"""Abstract interface for a character voice provider."""
from abc import ABC, abstractmethod

from src.characters.voice_candidate import VoiceCandidate
from src.domain.character import Character

DEFAULT_CANDIDATE_LIMIT = 5


class CharacterProvider(ABC):
    """Owns the lifecycle of voices for the characters in a book."""

    @abstractmethod
    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        """Ensure *character* has a voice on the vendor and return the token."""

    @abstractmethod
    def candidates(
        self, character: Character, limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> list[VoiceCandidate]:
        """Return at most *limit* voices *character* could be cast with, best first."""
