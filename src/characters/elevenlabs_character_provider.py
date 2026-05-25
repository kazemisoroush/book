"""ElevenLabs implementation of :class:`CharacterProvider`."""
from typing import Any, Optional

import structlog

from src.characters.character_provider import CharacterProvider
from src.domain.models import Book, Character

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = (
    "The morning light filtered through the window as she poured the tea. "
    "Outside, the birds were singing and the garden was beginning to bloom with colour."
)


class ElevenLabsCharacterProvider(CharacterProvider):
    """Character provider backed by the ElevenLabs Voice Design API."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def upsert(self, book: Book, character: Character) -> str:
        """Return a ``voice_id`` for *character*, designing one on cache miss."""
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
        return self._design_voice(
            description=description,
            voice_name=character.character_id,
        )

    def get_all(self, book: Book) -> dict[str, str]:
        """Return the ``character_id -> voice_id`` map for *book*."""
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

    def _design_voice(self, description: str, voice_name: str) -> str:
        """Create a permanent ElevenLabs voice and return its ``voice_id``."""
        preview = self._client.text_to_voice.create_previews(
            voice_description=description,
            text=_PREVIEW_TEXT,
        )
        generated_voice_id = preview.previews[0].generated_voice_id
        voice = self._client.text_to_voice.create(
            voice_name=voice_name,
            voice_description=description,
            generated_voice_id=generated_voice_id,
        )
        logger.info(
            "elevenlabs_voice_designed",
            voice_name=voice_name,
            voice_id=voice.voice_id,
        )
        return str(voice.voice_id)

    @staticmethod
    def _voice_design_prompt(character: Character) -> str:
        """Return a non-empty voice design prompt for *character*."""
        prompt = character.voice_design_prompt
        if prompt:
            return prompt
        if character.is_narrator:
            return "calm, warm narrator voice; neutral accent; steady pacing."
        return f"natural, expressive {character.name} voice."
