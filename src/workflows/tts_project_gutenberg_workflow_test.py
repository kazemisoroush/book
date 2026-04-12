"""Tests for TTSProjectGutenbergWorkflow feature flag threading."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config.feature_flags import FeatureFlags
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.audio.tts.voice_assigner import VoiceEntry
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


def test_create_instantiates_fish_audio_tts_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workflow.create() instantiates FishAudioTTSProvider as the TTS provider."""
    # Arrange
    from src.config import reload_config

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    reload_config()

    with patch("src.workflows.tts_project_gutenberg_workflow.FishAudioTTSProvider") as mock_fish_provider_cls, \
         patch("src.workflows.tts_project_gutenberg_workflow.AIProjectGutenbergWorkflow.create"):

        mock_provider_instance = MagicMock()
        mock_provider_instance.get_voices.return_value = [
            {"voice_id": "v1", "name": "Voice 1", "labels": {}}
        ]
        mock_fish_provider_cls.return_value = mock_provider_instance

        # Act
        workflow = TTSProjectGutenbergWorkflow.create()

        # Assert
        mock_fish_provider_cls.assert_called_once_with(api_key="test-fish-key")
        assert workflow._tts_provider == mock_provider_instance


def test_create_instantiates_stable_audio_ambient_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workflow.create() instantiates StableAudioAmbientProvider as the ambient provider."""
    # Arrange
    from src.config import reload_config

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
    monkeypatch.setenv("STABILITY_API_KEY", "test-stability-key")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    reload_config()

    with patch("src.workflows.tts_project_gutenberg_workflow.FishAudioTTSProvider") as mock_fish_cls, \
         patch("src.workflows.tts_project_gutenberg_workflow.StableAudioAmbientProvider") as mock_stable_cls, \
         patch("src.workflows.tts_project_gutenberg_workflow.AIProjectGutenbergWorkflow.create"):

        mock_fish_instance = MagicMock()
        mock_fish_instance.get_voices.return_value = [
            {"voice_id": "v1", "name": "Voice 1", "labels": {}}
        ]
        mock_fish_cls.return_value = mock_fish_instance

        mock_stable_instance = MagicMock()
        mock_stable_cls.return_value = mock_stable_instance

        # Act
        workflow = TTSProjectGutenbergWorkflow.create()

        # Assert
        mock_stable_cls.assert_called_once()
        args, kwargs = mock_stable_cls.call_args
        assert kwargs["api_key"] == "test-stability-key"
        assert isinstance(kwargs["cache_dir"], Path)
        assert workflow._ambient_provider == mock_stable_instance


def test_create_instantiates_suno_music_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workflow.create() instantiates SunoMusicProvider as the music provider."""
    # Arrange
    from src.config import reload_config

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
    monkeypatch.setenv("SUNO_API_KEY", "test-suno-key")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    reload_config()

    with patch("src.workflows.tts_project_gutenberg_workflow.FishAudioTTSProvider") as mock_fish_cls, \
         patch("src.workflows.tts_project_gutenberg_workflow.SunoMusicProvider") as mock_suno_cls, \
         patch("src.workflows.tts_project_gutenberg_workflow.AIProjectGutenbergWorkflow.create"):

        mock_fish_instance = MagicMock()
        mock_fish_instance.get_voices.return_value = [
            {"voice_id": "v1", "name": "Voice 1", "labels": {}}
        ]
        mock_fish_cls.return_value = mock_fish_instance

        mock_suno_instance = MagicMock()
        mock_suno_cls.return_value = mock_suno_instance

        # Act
        workflow = TTSProjectGutenbergWorkflow.create()

        # Assert
        mock_suno_cls.assert_called_once()
        args, kwargs = mock_suno_cls.call_args
        assert kwargs["api_key"] == "test-suno-key"
        assert isinstance(kwargs["cache_dir"], Path)
        assert workflow._music_provider == mock_suno_instance


# ------------------------------------------------------------------
# BOOK_TITLE: synthesize_introduction is no longer used (removed in Fix 2)
# Book title now flows through LLM → BOOK_TITLE segment → normal TTS
# ------------------------------------------------------------------


def test_workflow_does_not_call_synthesize_introduction(
    mock_ai_workflow: MagicMock,
    mock_voice_entries: list[VoiceEntry],
    mock_tts_provider: MagicMock,
    tmp_path: Path,
) -> None:
    """TTSProjectGutenbergWorkflow.run() must NOT call synthesize_introduction."""
    # Arrange
    from unittest.mock import patch

    workflow = TTSProjectGutenbergWorkflow(
        ai_workflow=mock_ai_workflow,
        voice_entries=mock_voice_entries,
        tts_provider=mock_tts_provider,
        books_dir=tmp_path,
    )

    with patch("src.workflows.tts_project_gutenberg_workflow.AudioOrchestrator") as MockOrch:
        mock_orch_instance = MagicMock()
        mock_orch_instance.synthesize_chapter.return_value = tmp_path / "ch1.mp3"
        MockOrch.return_value = mock_orch_instance

        # Act
        workflow.run(url="https://example.com/book.zip", end_chapter=1)

    # Assert — synthesize_introduction must never be called
    mock_orch_instance.synthesize_introduction.assert_not_called()
