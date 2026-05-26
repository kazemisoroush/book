"""Fish Audio implementation of :class:`CharacterProvider`."""
from src.characters.character_provider import CharacterProvider
from src.domain.character import Character
from src.domain.models import Book


class FishAudioCharacterProvider(CharacterProvider):
    """Stub character provider for Fish Audio."""

    def upsert(self, character: Character) -> str:
        raise NotImplementedError(
            "Fish Audio character creation is not implemented yet"
        )

    def get_all(self, book: Book) -> dict[str, str]:
        raise NotImplementedError(
            "Fish Audio character lookup is not implemented yet"
        )
