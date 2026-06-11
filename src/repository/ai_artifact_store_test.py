"""Tests for FileAIArtifactStore."""
import json
import os
import tempfile

from src.repository.ai_artifact_store import FileAIArtifactStore


class TestFileAIArtifactStore:
    """save_prompt and save_response write under ai/chapter_{NNN}/."""

    def test_writes_prompt_and_response_under_chapter_dir(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileAIArtifactStore(base_dir=tmp_dir)

            # Act
            store.save_prompt("alice", chapter_number=2, prompt="# Prompt")
            store.save_response(
                "alice", chapter_number=2,
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
            store = FileAIArtifactStore(base_dir=tmp_dir, use_book_id_subdir=False)

            # Act
            store.save_prompt("any-book", chapter_number=1, prompt="x")

            # Assert
            assert os.path.isfile(os.path.join(tmp_dir, "ai", "chapter_001", "prompt.md"))
