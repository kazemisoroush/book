"""Abstract interface for a character voice provider."""
from abc import ABC, abstractmethod

from src.domain.models import Book, Character


class CharacterProvider(ABC):
    """Owns the lifecycle of voices for the characters in a book.

    Each TTS vendor has its own implementation. The provider decides what a
    "voice token" is: for ElevenLabs it is the ``voice_id``; other vendors
    can use any opaque string that their TTSProvider accepts.

    Two operations:

    1. :meth:`upsert` makes sure *character* has a voice on the vendor side
       and returns the voice token. Implementations are expected to be
       idempotent ; calling upsert twice for the same character must return
       the same token.
    2. :meth:`get_all` returns the static ``character_id -> voice_token`` map
       for *book*. Implementations may read this from the book itself or
       from the vendor, whichever is the source of truth for that vendor.
    """

    @abstractmethod
    def upsert(self, book: Book, character: Character) -> str:
        """Make sure *character* has a voice on the vendor; return the token."""

    @abstractmethod
    def get_all(self, book: Book) -> dict[str, str]:
        """Return the ``character_id -> voice_token`` map for every character in *book*."""
