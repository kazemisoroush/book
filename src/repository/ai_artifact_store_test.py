"""Tests for FileAIArtifactStore."""
import json
import os
import tempfile

from src.repository.ai_artifact_store import FileAIArtifactStore


class TestFileAIArtifactStoreSavePrompt:
    """save_prompt writes prompt.md verbatim under ai/chapter_{NNN}/."""

    def test_writes_prompt_under_chapter_directory(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileAIArtifactStore(base_dir=tmp_dir)

            # Act
            store.save_prompt("alice", chapter_number=2, prompt="# Prompt text")

            # Assert
            path = os.path.join(tmp_dir, "alice", "ai", "chapter_002", "prompt.md")
            assert os.path.isfile(path)
            with open(path, "r", encoding="utf-8") as f:
                assert f.read() == "# Prompt text"


class TestFileAIArtifactStoreSaveResponse:
    """save_response writes response.json pretty-printed when valid JSON."""

    def test_writes_pretty_json_when_response_is_valid_json(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileAIArtifactStore(base_dir=tmp_dir)
            payload = json.dumps({"chapters": [{"id": 1, "beats": []}]})

            # Act
            store.save_response("alice", chapter_number=1, response=payload)

            # Assert
            path = os.path.join(tmp_dir, "alice", "ai", "chapter_001", "response.json")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "\n  " in content
            assert json.loads(content) == {"chapters": [{"id": 1, "beats": []}]}

    def test_writes_raw_text_when_response_is_not_json(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileAIArtifactStore(base_dir=tmp_dir)

            # Act
            store.save_response("alice", chapter_number=3, response="not json {")

            # Assert
            path = os.path.join(tmp_dir, "alice", "ai", "chapter_003", "response.json")
            with open(path, "r", encoding="utf-8") as f:
                assert f.read() == "not json {"


class TestFileAIArtifactStorePathPadding:
    """Chapter numbers are zero-padded to three digits in the directory name."""

    def test_chapter_directory_is_zero_padded(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileAIArtifactStore(base_dir=tmp_dir)

            # Act
            store.save_prompt("book", chapter_number=12, prompt="x")

            # Assert
            assert os.path.isdir(os.path.join(tmp_dir, "book", "ai", "chapter_012"))
