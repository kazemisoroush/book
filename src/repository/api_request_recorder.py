"""Generic helper that persists outbound API calls as JSON for inspection."""
import json
import shlex
from pathlib import Path
from typing import Any, Mapping

import structlog

logger = structlog.get_logger(__name__)

_AUTH_REDACTED = "Bearer ***"
_KEY_REDACTED = "***"
_SECRET_HEADER_NAMES = {"authorization", "xi-api-key", "x-api-key", "api-key"}


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Replace credential headers with a placeholder so artifacts are safe to commit."""
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower == "authorization":
            redacted[key] = _AUTH_REDACTED
        elif lower in _SECRET_HEADER_NAMES:
            redacted[key] = _KEY_REDACTED
        else:
            redacted[key] = value
    return redacted


def _build_curl(method: str, url: str, headers: Mapping[str, str], body: Any) -> str:
    """Return a copy-paste curl command equivalent to the recorded request."""
    parts = ["curl", "-X", method.upper(), shlex.quote(url)]
    for key, value in headers.items():
        parts.extend(["-H", shlex.quote(f"{key}: {value}")])
    if body is not None:
        parts.extend(["--data", shlex.quote(json.dumps(body, ensure_ascii=False))])
    return " ".join(parts)


def write_api_request(
    request_path: Path,
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Any,
) -> None:
    """Write an API call artifact to *request_path*.

    Args:
        request_path: Destination file, typically ending in ``.request.json``.
        method: HTTP method.
        url: Full URL of the endpoint.
        headers: Request headers. Credential headers are redacted.
        body: JSON-serializable request body, or ``None`` for GET-style calls.
    """
    redacted = _redact_headers(headers)
    payload = {
        "method": method.upper(),
        "url": url,
        "headers": redacted,
        "body": body,
        "curl": _build_curl(method, url, redacted, body),
    }
    request_path.parent.mkdir(parents=True, exist_ok=True)
    with open(request_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("api_request_saved", path=str(request_path))
