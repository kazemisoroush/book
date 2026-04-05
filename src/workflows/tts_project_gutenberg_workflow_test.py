"""Tests for TTSProjectGutenbergWorkflow feature flag threading."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
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
def mock_voice_assigner() -> MagicMock:
    """Create a mock VoiceAssigner."""
    mock = MagicMock()
    mock.assign.return_value = {"narrator": "voice_1"}
    return mock


@pytest.fixture
def mock_tts_provider() -> MagicMock:
    """Create a mock TTSProvider."""
    return MagicMock()


def test_workflow_accepts_emotion_enabled_parameter(
    mock_ai_workflow: MagicMock,
    mock_voice_assigner: MagicMock,
    mock_tts_provider: MagicMock,
    tmp_path: Path,
) -> None:
    """TTSProjectGutenbergWorkflow.run() accepts emotion_enabled parameter."""
    # Arrange
    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_assigner=mock_voice_assigner,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    # Act & Assert (should not raise)
    workflow.run(
        url="https://example.com/book.zip",
        chapter_limit=1,
        emotion_enabled=False,
    )


def test_workflow_accepts_voice_design_enabled_parameter(
    mock_ai_workflow: MagicMock,
    mock_voice_assigner: MagicMock,
    mock_tts_provider: MagicMock,
    tmp_path: Path,
) -> None:
    """TTSProjectGutenbergWorkflow.run() accepts voice_design_enabled parameter."""
    # Arrange
    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_assigner=mock_voice_assigner,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    # Act & Assert (should not raise)
    workflow.run(
        url="https://example.com/book.zip",
        chapter_limit=1,
        voice_design_enabled=False,
    )


def test_workflow_accepts_scene_context_enabled_parameter(
    mock_ai_workflow: MagicMock,
    mock_voice_assigner: MagicMock,
    mock_tts_provider: MagicMock,
    tmp_path: Path,
) -> None:
    """TTSProjectGutenbergWorkflow.run() accepts scene_context_enabled parameter."""
    # Arrange
    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_assigner=mock_voice_assigner,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    # Act & Assert (should not raise)
    workflow.run(
        url="https://example.com/book.zip",
        chapter_limit=1,
        scene_context_enabled=False,
    )


def test_workflow_passes_emotion_enabled_to_orchestrator(
    mock_ai_workflow: MagicMock,
    mock_voice_assigner: MagicMock,
    mock_tts_provider: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """emotion_enabled is passed to TTSOrchestrator constructor."""
    # Arrange
    from src.tts.tts_orchestrator import TTSOrchestrator

    captured_kwargs: dict = {}

    original_init = TTSOrchestrator.__init__

    def mock_init(self, *args, **kwargs):  # type: ignore
        captured_kwargs.update(kwargs)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TTSOrchestrator, "__init__", mock_init)

    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_assigner=mock_voice_assigner,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    # Act
    workflow.run(
        url="https://example.com/book.zip",
        chapter_limit=1,
        emotion_enabled=False,
    )

    # Assert
    assert "emotion_enabled" in captured_kwargs
    assert captured_kwargs["emotion_enabled"] is False


def test_workflow_passes_voice_design_enabled_to_orchestrator(
    mock_ai_workflow: MagicMock,
    mock_voice_assigner: MagicMock,
    mock_tts_provider: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """voice_design_enabled is passed to TTSOrchestrator constructor."""
    # Arrange
    from src.tts.tts_orchestrator import TTSOrchestrator

    captured_kwargs: dict = {}

    original_init = TTSOrchestrator.__init__

    def mock_init(self, *args, **kwargs):  # type: ignore
        captured_kwargs.update(kwargs)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TTSOrchestrator, "__init__", mock_init)

    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_assigner=mock_voice_assigner,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    # Act
    workflow.run(
        url="https://example.com/book.zip",
        chapter_limit=1,
        voice_design_enabled=False,
    )

    # Assert
    assert "voice_design_enabled" in captured_kwargs
    assert captured_kwargs["voice_design_enabled"] is False


def test_workflow_passes_scene_context_enabled_to_orchestrator(
    mock_ai_workflow: MagicMock,
    mock_voice_assigner: MagicMock,
    mock_tts_provider: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scene_context_enabled is passed to TTSOrchestrator constructor."""
    # Arrange
    from src.tts.tts_orchestrator import TTSOrchestrator

    captured_kwargs: dict = {}

    original_init = TTSOrchestrator.__init__

    def mock_init(self, *args, **kwargs):  # type: ignore
        captured_kwargs.update(kwargs)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TTSOrchestrator, "__init__", mock_init)

    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_assigner=mock_voice_assigner,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    # Act
    workflow.run(
        url="https://example.com/book.zip",
        chapter_limit=1,
        scene_context_enabled=False,
    )

    # Assert
    assert "scene_context_enabled" in captured_kwargs
    assert captured_kwargs["scene_context_enabled"] is False
