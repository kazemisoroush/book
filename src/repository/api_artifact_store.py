"""Outbound API request artifact store."""
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping

import structlog

logger = structlog.get_logger(__name__)

_AUTH_REDACTED = "Bearer ***"
_KEY_REDACTED = "***"
_SECRET_HEADER_NAMES = {"authorization", "xi-api-key", "x-api-key", "api-key"}


class APIArtifactStore(ABC):
    """Persistence interface for one outbound API call."""

    @abstractmethod
    def save_request(
        self,
        path: Path,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Any,
    ) -> None:
        """Persist one API request at *path*."""


class FileAPIArtifactStore(APIArtifactStore):
    """File-backed APIArtifactStore."""

    def save_request(
        self,
        path: Path,
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
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("api_request_saved", path=str(path))


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Redact credential headers."""
    out: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower == "authorization":
            out[key] = _AUTH_REDACTED
        elif lower in _SECRET_HEADER_NAMES:
            out[key] = _KEY_REDACTED
        else:
            out[key] = value
    return out
