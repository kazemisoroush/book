"""Per-chapter LLM prompt and response artifact writer."""
import json
from abc import ABC, abstractmethod
from typing import Optional

import structlog

from src.domain.models import Chapter
from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage

logger = structlog.get_logger(__name__)


class AIArtifactStore(ABC):
    """Writes the rendered prompt and raw model response for one chapter."""

    @abstractmethod
    def save_prompt(self, book_id: str, chapter: Chapter, prompt: str) -> None:
        """Persist the rendered prompt for *chapter*."""

    @abstractmethod
    def save_response(self, book_id: str, chapter: Chapter, response: str) -> None:
        """Persist the raw model response for *chapter*."""


class FileAIArtifactStore(AIArtifactStore):
    """Storage-backed AIArtifactStore writing under ``{book_id}/ai/{chapter.dir_slug}/``."""

    _PROMPT_FILENAME = "prompt.md"
    _RESPONSE_FILENAME = "response.json"

    def __init__(
        self,
        base_dir: Optional[str] = None,
        use_book_id_subdir: bool = True,
        storage: Optional[Storage] = None,
    ) -> None:
        if storage is None:
            storage = LocalStorage(base_dir if base_dir is not None else "books")
        self._storage = storage
        self._use_book_id_subdir = use_book_id_subdir

    def save_prompt(self, book_id: str, chapter: Chapter, prompt: str) -> None:
        key = self._key_for(book_id, chapter, self._PROMPT_FILENAME)
        self._storage.write_text(key, prompt)
        logger.info(
            "ai_prompt_saved", book_id=book_id, chapter=chapter.number, key=key,
        )

    def save_response(self, book_id: str, chapter: Chapter, response: str) -> None:
        key = self._key_for(book_id, chapter, self._RESPONSE_FILENAME)
        try:
            parsed = json.loads(response)
            payload = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            payload = response
        self._storage.write_text(key, payload)
        logger.info(
            "ai_response_saved", book_id=book_id, chapter=chapter.number, key=key,
        )

    def _key_for(self, book_id: str, chapter: Chapter, filename: str) -> str:
        if self._use_book_id_subdir:
            return f"{book_id}/ai/{chapter.dir_slug}/{filename}"
        return f"ai/{chapter.dir_slug}/{filename}"
