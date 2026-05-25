"""Fish Audio implementation of :class:`CharacterProvider`."""
from src.characters.character_provider import CharacterProvider
from src.domain.models import Book, Character


class FishAudioCharacterProvider(CharacterProvider):
    """Stub character provider for Fish Audio."""

    def upsert(self, character: Character) -> str:
        raise NotImplementedError(
            "Fish Audio character creation is not implemented yet"
        )

    def get_all(self, book: Book) -> dict[str, str]:
        return {
            c.character_id: c.voice_id
            for c in book.character_registry.characters
            if c.voice_id is not None
        }
