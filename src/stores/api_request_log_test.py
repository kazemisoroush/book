"""Tests for FileAPIRequestLog."""
import json
from pathlib import Path

from src.storage.local_storage import LocalStorage
from src.stores.api_request_log import FileAPIRequestLog


class TestFileAPIRequestLog:
    """save_request writes a JSON record with credentials redacted."""

    def test_writes_record_and_redacts_credentials(self, tmp_path: Path) -> None:
        # Arrange
        log = FileAPIRequestLog(storage=LocalStorage(tmp_path))

        # Act
        log.save_request(
            key="alice/voices/elizabeth/library_search.request.json",
            method="POST",
            url="https://api.example.com/x",
            headers={
                "xi-api-key": "sk-secret",
                "Authorization": "Bearer real-token",
                "Content-Type": "application/json",
            },
            body={"text": "Hello."},
        )

        # Assert
        path = tmp_path / "alice" / "voices" / "elizabeth" / "library_search.request.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["method"] == "POST"
        assert payload["url"] == "https://api.example.com/x"
        assert payload["headers"]["xi-api-key"] == "***"
        assert payload["headers"]["Authorization"] == "Bearer ***"
        assert payload["headers"]["Content-Type"] == "application/json"
        assert payload["body"] == {"text": "Hello."}
