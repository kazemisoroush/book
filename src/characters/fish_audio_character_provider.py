"""Fish Audio implementation of :class:`CharacterProvider`.

Fish Audio does not yet have a voice-from-text-description API. This
provider is a placeholder so the characters workflow can be invoked with
``--provider fish``; ``upsert`` raises :class:`NotImplementedError` until
a real strategy is wired in.
"""
from src.characters.character_provider import CharacterProvider
from src.domain.models import Book, Character


class FishAudioCharacterProvider(CharacterProvider):
    """Stub character provider for Fish Audio."""

    def upsert(self, book: Book, character: Character) -> str:
        raise NotImplementedError(
            "Fish Audio character creation is not implemented yet"
        )

    def get_all(self, book: Book) -> dict[str, str]:
        return {
            c.character_id: c.voice_id
            for c in book.character_registry.characters
            if c.voice_id is not None
        }
