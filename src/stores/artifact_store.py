"""Abstract artifact store for AI prompts/responses and outbound API requests."""
from abc import ABC, abstractmethod
from typing import Any, Mapping

from src.domain.models import Chapter


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
