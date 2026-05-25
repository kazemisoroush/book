"""ElevenLabs implementation of :class:`CharacterProvider`.

For each character, a designed voice is created on ElevenLabs the first
time and reused on subsequent runs. The character_id doubles as the voice
name on ElevenLabs, so a single ``voices.get_all(search=character_id)``
finds the existing voice on cache hits.
"""
from typing import Any, Optional

import structlog

from src.characters.character_provider import CharacterProvider
from src.characters.voice_designer import design_voice
from src.domain.models import Book, Character

logger = structlog.get_logger(__name__)


class ElevenLabsCharacterProvider(CharacterProvider):
    """Character provider backed by the ElevenLabs Voice Design API."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def upsert(self, book: Book, character: Character) -> str:
        """Return a ``voice_id`` for *character*, designing one if missing."""
        existing = self._find_voice_by_name(character.character_id)
        if existing is not None:
            logger.info(
                "elevenlabs_character_cache_hit",
                character_id=character.character_id,
                voice_id=existing,
            )
            return existing

        description = self._voice_design_prompt(character)
        logger.info(
            "elevenlabs_character_cache_miss",
            character_id=character.character_id,
            description=description,
        )
        return design_voice(
            description=description,
            voice_name=character.character_id,
            client=self._client,
        )

    def get_all(self, book: Book) -> dict[str, str]:
        """Return the ``character_id -> voice_id`` map for *book*.

        Source of truth is the book itself ; :meth:`upsert` stamps the
        ``voice_id`` field on each character and the workflow persists it
        between runs.
        """
        return {
            c.character_id: c.voice_id
            for c in book.character_registry.characters
            if c.voice_id is not None
        }

    def _find_voice_by_name(self, name: str) -> Optional[str]:
        try:
            response = self._client.voices.get_all(search=name)
        except Exception:
            logger.warning(
                "elevenlabs_voice_search_failed",
                name=name,
                exc_info=True,
            )
            return None
        for voice in response.voices:
            if voice.name == name:
                return str(voice.voice_id)
        return None

    @staticmethod
    def _voice_design_prompt(character: Character) -> str:
        """Return a non-empty voice design prompt for *character*."""
        prompt = character.voice_design_prompt
        if prompt:
            return prompt
        if character.is_narrator:
            return "calm, warm narrator voice; neutral accent; steady pacing."
        return f"natural, expressive {character.name} voice."
