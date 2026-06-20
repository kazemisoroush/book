"""Unified artifact store for AI prompts/responses and outbound API requests."""
import json
from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

import structlog

from src.domain.models import Chapter
from src.storage.local_file_storage import LocalFileStorage
from src.storage.storage import Storage

logger = structlog.get_logger(__name__)

_AUTH_REDACTED = "Bearer ***"
_KEY_REDACTED = "***"
_SECRET_HEADER_NAMES = {"authorization", "xi-api-key", "x-api-key", "api-key"}


class ArtifactStore(ABC):
    """Persists AI chapter artifacts and outbound API request records."""

    @abstractmethod
    def save_prompt(self, book_id: str, chapter: Chapter, prompt: str) -> None:
        """Persist the rendered prompt for *chapter*."""

    @abstractmethod
    def save_response(self, book_id: str, chapter: Chapter, response: str) -> None:
        """Persist the raw model response for *chapter*."""

    @abstractmethod
    def save_request(
        self,
        key: str,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Any,
    ) -> None:
        """Persist one outbound API request at *key* with credentials redacted."""


class FileArtifactStore(ArtifactStore):
    """Storage-backed artifact store for AI artifacts and API request records."""

    _PROMPT_FILENAME = "prompt.md"
    _RESPONSE_FILENAME = "response.json"

    def __init__(
        self,
        base_dir: Optional[str] = None,
        use_book_id_subdir: bool = True,
        storage: Optional[Storage] = None,
    ) -> None:
        if storage is None:
            storage = LocalFileStorage(base_dir if base_dir is not None else "books")
        self._storage = storage
        self._use_book_id_subdir = use_book_id_subdir

    def save_prompt(self, book_id: str, chapter: Chapter, prompt: str) -> None:
        key = self._chapter_key(book_id, chapter, self._PROMPT_FILENAME)
        self._storage.write_text(key, prompt)
        logger.info(
            "ai_prompt_saved", book_id=book_id, chapter=chapter.number, key=key,
        )

    def save_response(self, book_id: str, chapter: Chapter, response: str) -> None:
        key = self._chapter_key(book_id, chapter, self._RESPONSE_FILENAME)
        try:
            parsed = json.loads(response)
            payload = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            payload = response
        self._storage.write_text(key, payload)
        logger.info(
            "ai_response_saved", book_id=book_id, chapter=chapter.number, key=key,
        )

    def save_request(
        self,
        key: str,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Any,
    ) -> None:
        payload = {
            "method": method.upper(),
            "url": url,
            "headers": _redact_headers(headers),
            "body": body,
        }
        self._storage.write_text(
            key, json.dumps(payload, indent=2, ensure_ascii=False),
        )
        logger.info("api_request_saved", key=key)

    def _chapter_key(self, book_id: str, chapter: Chapter, filename: str) -> str:
        if self._use_book_id_subdir:
            return f"{book_id}/ai/{chapter.dir_slug}/{filename}"
        return f"ai/{chapter.dir_slug}/{filename}"


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Redact credential headers."""
    out: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower == "authorization":
            out[name] = _AUTH_REDACTED
        elif lower in _SECRET_HEADER_NAMES:
            out[name] = _KEY_REDACTED
        else:
            out[name] = value
    return out
