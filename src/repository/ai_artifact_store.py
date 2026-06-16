"""Per-chapter LLM prompt and response artifact writer."""
import json
import os
from abc import ABC, abstractmethod

import structlog

from src.domain.models import Chapter

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
    """File-backed AIArtifactStore writing under ``{base_dir}/{book_id}/ai/{chapter.dir_slug}/``."""

    _PROMPT_FILENAME = "prompt.md"
    _RESPONSE_FILENAME = "response.json"

    def __init__(self, base_dir: str = "books", use_book_id_subdir: bool = True) -> None:
        self._base_dir = base_dir
        self._use_book_id_subdir = use_book_id_subdir

    def save_prompt(self, book_id: str, chapter: Chapter, prompt: str) -> None:
        path = self._path_for(book_id, chapter, self._PROMPT_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(prompt)
        logger.info(
            "ai_prompt_saved", book_id=book_id, chapter=chapter.number, path=path,
        )

    def save_response(self, book_id: str, chapter: Chapter, response: str) -> None:
        path = self._path_for(book_id, chapter, self._RESPONSE_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            parsed = json.loads(response)
            payload = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            payload = response
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        logger.info(
            "ai_response_saved", book_id=book_id, chapter=chapter.number, path=path,
        )

    def _path_for(self, book_id: str, chapter: Chapter, filename: str) -> str:
        if self._use_book_id_subdir:
            return os.path.join(
                self._base_dir, book_id, "ai", chapter.dir_slug, filename,
            )
        return os.path.join(self._base_dir, "ai", chapter.dir_slug, filename)
