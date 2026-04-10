"""Tests for TTSProjectGutenbergWorkflow feature flag threading."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config.feature_flags import FeatureFlags
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.tts.voice_assigner import VoiceEntry
from src.workflows.tts_project_gutenberg_workflow import TTSProjectGutenbergWorkflow


@pytest.fixture
def mock_ai_workflow() -> MagicMock:
    """Create a mock AIProjectGutenbergWorkflow."""
    mock = MagicMock()
    # Create a minimal book for the workflow to return
    metadata = BookMetadata(
        title="Test",
        author="Test Author",
        language="en",
        releaseDate=None,
        originalPublication=None,
        credits=None,
    )
    content = BookContent(chapters=[
        Chapter(number=1, title="Chapter 1", sections=[
            Section(text="Test section.", section_type=None, segments=None)
        ])
    ])
    book = Book(metadata=metadata, content=content)
    mock.run.return_value = book
    return mock


@pytest.fixture
def mock_voice_entries() -> list[VoiceEntry]:
    """Create a list of mock voice entries."""
    return [
        VoiceEntry(voice_id="v1", name="Voice 1", labels={}),
        VoiceEntry(voice_id="v2", name="Voice 2", labels={}),
    ]


@pytest.fixture
def mock_tts_provider() -> MagicMock:
    """Create a mock TTSProvider."""
    return MagicMock()


def test_workflow_accepts_feature_flags(
    mock_ai_workflow: MagicMock,
    mock_voice_entries: list[VoiceEntry],
    mock_tts_provider: MagicMock,
    tmp_path: Path,
) -> None:
    """TTSProjectGutenbergWorkflow.run() accepts feature_flags parameter."""
    # Arrange
    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_entries=mock_voice_entries,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )
    flags = FeatureFlags(emotion_enabled=False, voice_design_enabled=False)

    # Act & Assert (should not raise)
    workflow.run(
        url="https://example.com/book.zip",
        end_chapter=1,
        feature_flags=flags,
    )
