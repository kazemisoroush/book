"""Fish Audio implementation of :class:`CharacterProvider`."""
from src.characters.character_provider import (
    DEFAULT_CANDIDATE_LIMIT,
    CharacterProvider,
)
from src.characters.voice_candidate import VoiceCandidate
from src.domain.character import Character


class FishAudioCharacterProvider(CharacterProvider):
    """Stub character provider for Fish Audio."""

    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        raise NotImplementedError(
            "Fish Audio character creation is not implemented yet"
        )

    def candidates(
        self, character: Character, limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> list[VoiceCandidate]:
        raise NotImplementedError(
            "Fish Audio voice candidates are not implemented yet"
        )
