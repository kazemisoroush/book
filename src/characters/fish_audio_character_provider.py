"""Fish Audio implementation of :class:`CharacterProvider`."""
from src.characters.character_provider import CharacterProvider
from src.domain.character import Character


class FishAudioCharacterProvider(CharacterProvider):
    """Stub character provider for Fish Audio."""

    def upsert(self, character: Character, book_id: str) -> str:
        raise NotImplementedError(
            "Fish Audio character creation is not implemented yet"
        )
