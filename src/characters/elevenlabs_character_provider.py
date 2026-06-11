"""ElevenLabs implementation of :class:`CharacterProvider`."""
import base64
from pathlib import Path
from typing import Any, Optional

import structlog

from src.characters.character_provider import CharacterProvider
from src.domain.character import Character
from src.domain.character_id import build_character_id
from src.repository.api_request_recorder import write_api_request

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = (
    "The morning light filtered through the window as she poured the tea. "
    "Outside, the birds were singing and the garden was beginning to bloom with colour."
)

_VOICES_SEARCH_URL = "https://api.elevenlabs.io/v1/voices"
_CREATE_PREVIEWS_URL = "https://api.elevenlabs.io/v1/text-to-voice/create-previews"
_CREATE_URL = "https://api.elevenlabs.io/v1/text-to-voice"


class ElevenLabsCharacterProvider(CharacterProvider):
    """Character provider backed by the ElevenLabs Voice Design API."""

    def __init__(
        self, client: Any, books_dir: Path, api_key: str = "",
    ) -> None:
        self._client = client
        self._books_dir = books_dir
        self._api_key = api_key

    def upsert(self, character: Character, book_id: str) -> str:
        """Return a ``voice_id`` for *character*, creating one on cache miss."""
        slug = build_character_id(book_id, character.name)
        existing = self._search(slug)
        if existing is not None:
            logger.info("elevenlabs_voice_cache_hit", name=slug, voice_id=existing)
            return existing

        description = character.voice_design_prompt
        if description is None:
            raise ValueError(
                f"Character {slug!r} has no voice description; "
                "set `description` before calling upsert()."
            )
        return self._create(slug, description)

    def _search(self, name: str) -> Optional[str]:
        """Return the ``voice_id`` of the ElevenLabs voice exactly named *name*, or None."""
        write_api_request(
            request_path=self._voice_dir(name) / "search.request.json",
            method="GET",
            url=f"{_VOICES_SEARCH_URL}?search={name}",
            headers={"xi-api-key": self._api_key, "Accept": "application/json"},
            body=None,
        )
        try:
            response = self._client.voices.search(search=name)
        except Exception as exc:
            logger.warning("elevenlabs_voice_search_failed", name=name, error=str(exc))
            return None
        for voice in response.voices:
            if voice.name == name:
                return str(voice.voice_id)
        return None

    def _create(self, name: str, description: str) -> str:
        """Design a new ElevenLabs voice named *name* and return its ``voice_id``."""
        voice_dir = self._voice_dir(name)
        write_api_request(
            request_path=voice_dir / "create_previews.request.json",
            method="POST",
            url=_CREATE_PREVIEWS_URL,
            headers={
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            body={"voice_description": description, "text": _PREVIEW_TEXT},
        )
        preview = self._client.text_to_voice.create_previews(
            voice_description=description,
            text=_PREVIEW_TEXT,
        )
        self._save_previews(name, preview.previews)
        generated_voice_id = preview.previews[0].generated_voice_id
        write_api_request(
            request_path=voice_dir / "create.request.json",
            method="POST",
            url=_CREATE_URL,
            headers={
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            body={
                "voice_name": name,
                "voice_description": description,
                "generated_voice_id": generated_voice_id,
            },
        )
        voice = self._client.text_to_voice.create(
            voice_name=name,
            voice_description=description,
            generated_voice_id=generated_voice_id,
        )
        logger.info("elevenlabs_voice_created", name=name, voice_id=voice.voice_id)
        return str(voice.voice_id)

    def _voice_dir(self, slug: str) -> Path:
        """Return the per-character ``voices/{slug}`` dir under the book."""
        book_id, _, character_slug = slug.rpartition(":")
        return self._books_dir / book_id / "voices" / character_slug

    def _save_previews(self, slug: str, previews: list[Any]) -> None:
        """Decode every preview's base64 audio and write it to disk for later auditioning."""
        preview_dir = self._voice_dir(slug)
        preview_dir.mkdir(parents=True, exist_ok=True)
        for index, preview in enumerate(previews):
            (preview_dir / f"preview_{index}.mp3").write_bytes(
                base64.b64decode(preview.audio_base_64),
            )
        logger.info(
            "elevenlabs_previews_saved",
            slug=slug,
            count=len(previews),
            directory=str(preview_dir),
        )
