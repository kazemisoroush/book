"""Tests for FileArtifactRepository."""
import json
import os
import tempfile
from pathlib import Path

from src.domain.models import Chapter
from src.repository.file_artifact_repository import FileArtifactRepository
from src.storage.local_storage import LocalStorage


class TestFileArtifactRepositoryAI:
    """save_prompt and save_response write under ai/{chapter.dir_slug}/."""

    def test_writes_prompt_and_response_under_chapter_dir(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileArtifactRepository(base_dir=tmp_dir)
            chapter = Chapter(number=2, title="")

            # Act
            store.save_prompt("alice", chapter, prompt="# Prompt")
            store.save_response(
                "alice", chapter,
                response=json.dumps({"chapters": []}),
            )

            # Assert
            base = os.path.join(tmp_dir, "alice", "ai", "chapter_002")
            with open(os.path.join(base, "prompt.md"), encoding="utf-8") as f:
                assert f.read() == "# Prompt"
            with open(os.path.join(base, "response.json"), encoding="utf-8") as f:
                assert json.loads(f.read()) == {"chapters": []}

    def test_no_book_id_subdir_writes_under_base_dir(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileArtifactRepository(base_dir=tmp_dir, use_book_id_subdir=False)

            # Act
            store.save_prompt("any-book", Chapter(number=1, title=""), prompt="x")

            # Assert
            assert os.path.isfile(os.path.join(tmp_dir, "ai", "chapter_001", "prompt.md"))


class TestFileArtifactRepositoryRequest:
    """save_request writes a JSON record with credentials redacted."""

    def test_writes_record_and_redacts_credentials(self, tmp_path: Path) -> None:
        # Arrange
        store = FileArtifactRepository(storage=LocalStorage(tmp_path))

        # Act
        store.save_request(
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
