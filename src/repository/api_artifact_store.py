"""Outbound API request artifact store."""
import json
from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

import structlog

from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage

logger = structlog.get_logger(__name__)

_AUTH_REDACTED = "Bearer ***"
_KEY_REDACTED = "***"
_SECRET_HEADER_NAMES = {"authorization", "xi-api-key", "x-api-key", "api-key"}


class APIArtifactStore(ABC):
    """Persistence interface for one outbound API call."""

    @abstractmethod
    def save_request(
        self,
        key: str,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Any,
    ) -> None:
        """Persist one API request at *key*."""


class FileAPIArtifactStore(APIArtifactStore):
    """Storage-backed APIArtifactStore."""

    def __init__(self, storage: Optional[Storage] = None) -> None:
        if storage is None:
            storage = LocalStorage("books")
        self._storage = storage

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
            key,
            json.dumps(payload, indent=2, ensure_ascii=False),
        )
        logger.info("api_request_saved", key=key)


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
