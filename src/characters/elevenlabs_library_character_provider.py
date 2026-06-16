"""ElevenLabs Voice Library implementation of :class:`CharacterProvider`."""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.characters.character_provider import CharacterProvider
from src.domain.character import Character
from src.domain.character_id import build_character_id
from src.repository.api_artifact_store import APIArtifactStore

logger = structlog.get_logger(__name__)

_SHARED_VOICES_URL = "https://api.elevenlabs.io/v1/shared-voices"
_VOICES_SEARCH_URL = "https://api.elevenlabs.io/v2/voices"
_ADD_SHARED_URL = "https://api.elevenlabs.io/v1/voices/add/{public_owner_id}/{voice_id}"


class ElevenLabsLibraryCharacterProvider(CharacterProvider):
    """Character provider that picks a matching voice from the shared library."""

    def __init__(
        self,
        client: Any,
        books_dir: Path,
        book_language: str = "en",
        api_key: str = "",
        artifact_store: Optional[APIArtifactStore] = None,
    ) -> None:
        self._client = client
        self._books_dir = books_dir
        self._book_language = book_language
        self._api_key = api_key
        self._artifact_store = artifact_store
        self._assigned_shared_voice_ids: set[str] = set()

    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        """Return a ``voice_id`` for *character*, picking from the library on cache miss or refresh."""
        slug = build_character_id(book_id, character.name)
        if not refresh:
            existing = self._search_library(slug)
            if existing is not None:
                logger.info(
                    "elevenlabs_library_cache_hit", name=slug, voice_id=existing,
                )
                return existing

        picked = self._pick_from_shared(character)
        if picked is None:
            raise ValueError(
                f"No shared voice matched character {slug!r} "
                f"(gender={character.gender!r}, age={character.age!r}, "
                f"accent={character.accent!r})."
            )
        self._assigned_shared_voice_ids.add(str(picked.voice_id))
        return self._add_to_workspace(slug, picked)

    def _search_library(self, name: str) -> Optional[str]:
        if self._artifact_store is not None:
            self._artifact_store.save_request(
                path=self._voice_dir(name) / "library_search.request.json",
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

    def _pick_from_shared(self, character: Character) -> Optional[Any]:
        """Try the full filter set, then relax in order: accent -> age."""
        relaxation_steps: list[tuple[Optional[str], Optional[str]]] = [
            (character.accent, character.age),
            (None, character.age),
            (None, None),
        ]
        for relaxed_accent, relaxed_age in relaxation_steps:
            voice = self._query_shared(
                gender=character.gender,
                age=relaxed_age,
                accent=relaxed_accent,
            )
            if voice is not None:
                logger.info(
                    "elevenlabs_library_picked",
                    voice_id=voice.voice_id,
                    voice_name=getattr(voice, "name", None),
                    accent=relaxed_accent,
                    age=relaxed_age,
                )
                return voice
        return None

    def _query_shared(
        self,
        *,
        gender: Optional[str],
        age: Optional[str],
        accent: Optional[str],
    ) -> Optional[Any]:
        kwargs: dict[str, Any] = {
            "language": self._book_language,
            "category": "professional",
            "sort": "trending",
            "page_size": 100,
        }
        if gender is not None:
            kwargs["gender"] = gender
        if age is not None:
            kwargs["age"] = age
        if accent is not None:
            kwargs["accent"] = accent
        if self._artifact_store is not None:
            self._artifact_store.save_request(
                path=self._books_dir / "_shared_voices" / "shared_search.request.json",
                method="GET",
                url=_SHARED_VOICES_URL,
                headers={"xi-api-key": self._api_key, "Accept": "application/json"},
                body=kwargs,
            )
        try:
            response = self._client.voices.get_shared(**kwargs)
        except Exception as exc:
            logger.warning(
                "elevenlabs_library_query_failed",
                error=str(exc), kwargs=kwargs,
            )
            return None
        for voice in response.voices:
            if not getattr(voice, "free_users_allowed", True):
                continue
            if str(voice.voice_id) in self._assigned_shared_voice_ids:
                continue
            return voice
        return None

    def _add_to_workspace(self, name: str, shared_voice: Any) -> str:
        owner_id = shared_voice.public_owner_id
        shared_voice_id = shared_voice.voice_id
        if self._artifact_store is not None:
            self._artifact_store.save_request(
                path=self._voice_dir(name) / "add_shared.request.json",
                method="POST",
                url=_ADD_SHARED_URL.format(
                    public_owner_id=owner_id, voice_id=shared_voice_id,
                ),
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                body={"new_name": name},
            )
        added = self._client.voices.share(
            owner_id,
            shared_voice_id,
            new_name=name,
        )
        added_voice_id = str(added.voice_id)
        logger.info(
            "elevenlabs_library_voice_added",
            name=name, voice_id=added_voice_id,
            shared_voice_id=shared_voice_id, owner_id=owner_id,
        )
        return added_voice_id

    def _voice_dir(self, slug: str) -> Path:
        """Return the per-character ``voices/{slug}`` dir under the book."""
        book_id, _, character_slug = slug.rpartition(":")
        return self._books_dir / book_id / "voices" / character_slug
