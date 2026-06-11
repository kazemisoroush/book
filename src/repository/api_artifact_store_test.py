"""Tests for FileAPIArtifactStore."""
import json
from pathlib import Path

from src.repository.api_artifact_store import FileAPIArtifactStore


class TestFileAPIArtifactStore:
    """save_request writes a JSON artifact with credentials redacted."""

    def test_writes_and_redacts(self, tmp_path: Path) -> None:
        # Arrange
        store = FileAPIArtifactStore()
        path = tmp_path / "voices" / "alice" / "search.request.json"

        # Act
        store.save_request(
            path=path,
            method="POST",
            url="https://api.example.com/x",
            headers={"xi-api-key": "sk-secret", "Content-Type": "application/json"},
            body={"text": "Hello."},
        )

        # Assert
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["method"] == "POST"
        assert payload["url"] == "https://api.example.com/x"
        assert payload["headers"]["xi-api-key"] == "***"
        assert payload["headers"]["Content-Type"] == "application/json"
        assert payload["body"] == {"text": "Hello."}
