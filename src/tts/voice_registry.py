"""ElevenLabs voice lifecycle management — lookup-before-create.

Manages the voice lifecycle in the ElevenLabs account.  Before creating a new
designed voice, searches for an existing voice by a deterministic key derived
from the book metadata and character ID.  Returns the existing voice_id on
cache hit, or delegates to ``design_voice()`` to create a new one on miss.

This prevents duplicate voices from accumulating in the ElevenLabs account and
ensures voice consistency across re-runs.

## Deterministic voice key

Each designed voice is identified by:

    {book_title}::{book_author}::{character_id}

For example: ``Pride and Prejudice::Jane Austen::mr_bennet``

This key is stored as the ``voice_name`` in ElevenLabs when creating the voice,
and looked up via the ``GET /v2/voices?search=`` endpoint on subsequent runs.

## Lookup-before-create flow

1. Derive the deterministic key from book metadata and character ID.
2. Search the ElevenLabs voice library for voices matching the key.
3. If an exact name match is found, return its ``voice_id`` immediately (cache hit).
4. If no match, call ``design_voice()`` to create a new voice with the key as
   its ``voice_name`` (cache miss).
5. If the search API fails, log a warning and fall through to voice creation.
"""
from typing import Any

import structlog

from src.tts.voice_designer import design_voice

logger = structlog.get_logger(__name__)


class ElevenLabsVoiceRegistry:
    """Manages voice lifecycle in the ElevenLabs account.

    Lookup-before-create: searches for an existing voice by deterministic
    key, returns its voice_id on hit, or delegates to voice_designer to
    create a new one on miss.
    """

    def __init__(self, client: Any) -> None:
        """Initialise with an ElevenLabs SDK client.

        Args:
            client: An initialised ``ElevenLabs`` SDK client instance.
        """
        self._client = client

    def get_or_create_voice(
        self,
        book_title: str,
        book_author: str,
        character_id: str,
        voice_description: str,
        character_name: str,
    ) -> str:
        """Return a voice_id, creating one only if it doesn't exist.

        Derives a deterministic key from the book metadata and character ID,
        searches the ElevenLabs voice library, and returns an existing
        voice_id if found.  If no match exists, creates a new voice via
        ``design_voice()`` using the key as the voice name.

        Args:
            book_title: The title of the book.
            book_author: The author of the book.
            character_id: The character's unique ID in the registry.
            voice_description: The voice design prompt for this character.
            character_name: The character's display name (unused, for signature compatibility).

        Returns:
            The ``voice_id`` of the existing or newly created voice.

        Raises:
            Any exception propagated from ``design_voice()`` on cache miss.
        """
        # Step 1: Derive deterministic key
        key = f"{book_title}::{book_author}::{character_id}"

        # Step 2: Search for existing voice
        try:
            response = self._client.voices.get_all(search=key)
            # Step 3: Filter for exact name match (search is fuzzy)
            for voice in response.voices:
                if voice.name == key:
                    logger.info(
                        "voice_cache_hit",
                        key=key,
                        voice_id=voice.voice_id,
                    )
                    return str(voice.voice_id)
        except Exception:
            logger.warning(
                "voice_search_failed",
                key=key,
                exc_info=True,
            )

        # Step 4: Cache miss — create new voice
        logger.info("voice_cache_miss", key=key)
        designed_id = design_voice(
            description=voice_description,
            character_name=key,
            client=self._client,
        )
        return designed_id
