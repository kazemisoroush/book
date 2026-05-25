"""ElevenLabs implementation of :class:`CharacterProvider`."""
from typing import Any, Optional

import structlog

from src.characters.character_provider import CharacterProvider
from src.domain.models import Book, Character
from src.repository.book_id import generate_book_id

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = (
    "The morning light filtered through the window as she poured the tea. "
    "Outside, the birds were singing and the garden was beginning to bloom with colour."
)


class ElevenLabsCharacterProvider(CharacterProvider):
    """Character provider backed by the ElevenLabs Voice Design API."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def upsert(self, character: Character) -> str:
        """Return a ``voice_id`` for *character*, creating one on cache miss."""
        existing = self._search(character.character_id)
        if existing is not None:
            logger.info(
                "elevenlabs_voice_cache_hit",
                name=character.character_id,
                voice_id=existing,
            )
            return existing

        description = character.voice_design_prompt
        if description is None:
            raise ValueError(
                f"Character {character.character_id!r} has no voice description; "
                "set `description` before calling upsert()."
            )
        return self._create(character.character_id, description)

    def _search(self, name: str) -> Optional[str]:
        """Return the ``voice_id`` of the ElevenLabs voice exactly named *name*, or None."""
        try:
            response = self._client.voices.get_all(search=name)
        except Exception:
            logger.warning("elevenlabs_voice_search_failed", name=name, exc_info=True)
            return None
        for voice in response.voices:
            if voice.name == name:
                return str(voice.voice_id)
        return None

    def _create(self, name: str, description: str) -> str:
        """Design a new ElevenLabs voice named *name* and return its ``voice_id``."""
        preview = self._client.text_to_voice.create_previews(
            voice_description=description,
            text=_PREVIEW_TEXT,
        )
        generated_voice_id = preview.previews[0].generated_voice_id
        voice = self._client.text_to_voice.create(
            voice_name=name,
            voice_description=description,
            generated_voice_id=generated_voice_id,
        )
        logger.info("elevenlabs_voice_created", name=name, voice_id=voice.voice_id)
        return str(voice.voice_id)

    def get_all(self, book: Book) -> dict[str, str]:
        """Return the ``character_id -> voice_id`` map currently on ElevenLabs for *book*."""
        prefix = f"{generate_book_id(book.metadata)}:"
        try:
            response = self._client.voices.get_all(search=prefix)
        except Exception:
            logger.warning("elevenlabs_voices_list_failed", prefix=prefix, exc_info=True)
            return {}
        return {
            voice.name: str(voice.voice_id)
            for voice in response.voices
            if voice.name.startswith(prefix)
        }
