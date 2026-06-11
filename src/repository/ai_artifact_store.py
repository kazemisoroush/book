"""Per-chapter LLM prompt and response artifact writer."""
import json
import os
from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger(__name__)


class AIArtifactStore(ABC):
    """Writes the rendered prompt and raw model response for one chapter."""

    @abstractmethod
    def save_prompt(self, book_id: str, chapter_number: int, prompt: str) -> None:
        """Persist the rendered prompt string for a chapter."""

    @abstractmethod
    def save_response(self, book_id: str, chapter_number: int, response: str) -> None:
        """Persist the raw model response (expected to be JSON) for a chapter."""


class FileAIArtifactStore(AIArtifactStore):
    """File-backed AIArtifactStore writing under ``{base_dir}/{book_id}/ai/chapter_{NNN}/``."""

    _PROMPT_FILENAME = "prompt.md"
    _RESPONSE_FILENAME = "response.json"

    def __init__(self, base_dir: str = "books", use_book_id_subdir: bool = True) -> None:
        self._base_dir = base_dir
        self._use_book_id_subdir = use_book_id_subdir

    def save_prompt(self, book_id: str, chapter_number: int, prompt: str) -> None:
        path = self._path_for(book_id, chapter_number, self._PROMPT_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(prompt)
        logger.info(
            "ai_prompt_saved", book_id=book_id, chapter=chapter_number, path=path,
        )

    def save_response(self, book_id: str, chapter_number: int, response: str) -> None:
        path = self._path_for(book_id, chapter_number, self._RESPONSE_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            parsed = json.loads(response)
            payload = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            payload = response
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        logger.info(
            "ai_response_saved", book_id=book_id, chapter=chapter_number, path=path,
        )

    def _path_for(self, book_id: str, chapter_number: int, filename: str) -> str:
        chapter_dir = f"chapter_{chapter_number:03d}"
        if self._use_book_id_subdir:
            return os.path.join(
                self._base_dir, book_id, "ai", chapter_dir, filename,
            )
        return os.path.join(self._base_dir, "ai", chapter_dir, filename)
