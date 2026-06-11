"""Tests for write_api_request."""
import json
from pathlib import Path

from src.repository.api_request_recorder import write_api_request


class TestWriteApiRequestFile:
    """write_api_request writes the artifact at the given path."""

    def test_writes_request_json_at_given_path(self, tmp_path: Path) -> None:
        # Arrange
        request_path = tmp_path / "audio" / "beat_0001.request.json"

        # Act
        write_api_request(
            request_path=request_path,
            method="POST",
            url="https://api.example.com/tts",
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
            body={"text": "Hello.", "voice_id": "vid"},
        )

        # Assert
        assert request_path.is_file()
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert payload["method"] == "POST"
        assert payload["url"] == "https://api.example.com/tts"
        assert payload["headers"]["Authorization"] == "Bearer ***"
        assert payload["headers"]["Content-Type"] == "application/json"
        assert payload["body"] == {"text": "Hello.", "voice_id": "vid"}


class TestWriteApiRequestNoBody:
    """body=None is preserved as null in the artifact."""

    def test_body_none_serialized_as_null(self, tmp_path: Path) -> None:
        # Arrange
        request_path = tmp_path / "voices.request.json"

        # Act
        write_api_request(
            request_path=request_path,
            method="GET",
            url="https://api.example.com/voices",
            headers={"Authorization": "Bearer secret"},
            body=None,
        )

        # Assert
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert payload["method"] == "GET"
        assert payload["body"] is None


class TestWriteApiRequestRedaction:
    """Credential headers are redacted; non-credential headers pass through."""

    def test_case_insensitive_authorization_is_redacted(self, tmp_path: Path) -> None:
        # Arrange
        request_path = tmp_path / "beat_0001.request.json"

        # Act
        write_api_request(
            request_path=request_path,
            method="POST",
            url="https://api.example.com/tts",
            headers={"authorization": "Bearer secret-value", "X-Trace": "abc"},
            body=None,
        )

        # Assert
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert payload["headers"]["authorization"] == "Bearer ***"
        assert payload["headers"]["X-Trace"] == "abc"

    def test_xi_api_key_is_redacted(self, tmp_path: Path) -> None:
        # Arrange
        request_path = tmp_path / "beat_0002.request.json"

        # Act
        write_api_request(
            request_path=request_path,
            method="POST",
            url="https://api.elevenlabs.io/v1/text-to-speech/vid",
            headers={"xi-api-key": "sk-secret", "Content-Type": "application/json"},
            body={"text": "Hi."},
        )

        # Assert
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert payload["headers"]["xi-api-key"] == "***"
        assert payload["headers"]["Content-Type"] == "application/json"
