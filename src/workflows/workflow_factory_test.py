"""Tests for workflow factory."""
from unittest.mock import patch

import pytest

from src.config.config import reload_config
from src.workflows.workflow_factory import create_workflow


def test_create_workflow_raises_on_unknown_name() -> None:
    """create_workflow() raises ValueError for unknown workflow names."""
    # Act & Assert
    with pytest.raises(ValueError, match="Unknown workflow"):
        create_workflow("unknown-workflow")


def test_create_parse_workflow_runs() -> None:
    """'parse' factory returns a workflow that has a run method."""
    # Act
    workflow = create_workflow("parse")

    # Assert
    assert callable(getattr(workflow, "run", None))


def test_create_ai_workflow_runs() -> None:
    """'ai' factory returns a workflow that has a run method."""
    # Act
    workflow = create_workflow("ai")

    # Assert
    assert callable(getattr(workflow, "run", None))


def test_create_tts_workflow_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """'tts' factory creates a workflow when API key is set."""
    # Arrange
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-key")
    reload_config()

    # Act
    with patch("src.audio.tts.fish_audio_tts_provider.FishAudioTTSProvider.get_voices",
               return_value=[{"voice_id": "v1", "name": "Voice 1", "labels": {}}]):
        workflow = create_workflow("tts")

    # Assert
    assert callable(getattr(workflow, "run", None))


def test_create_sfx_workflow_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """'sfx' factory creates a workflow when API key is set."""
    # Arrange
    monkeypatch.setenv("STABILITY_API_KEY", "test-key")
    reload_config()

    # Act
    workflow = create_workflow("sfx")

    # Assert
    assert callable(getattr(workflow, "run", None))


def test_create_ambient_workflow_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """'ambient' factory creates a workflow when API key is set."""
    # Arrange
    monkeypatch.setenv("STABILITY_API_KEY", "test-key")
    reload_config()

    # Act
    workflow = create_workflow("ambient")

    # Assert
    assert callable(getattr(workflow, "run", None))


def test_create_music_workflow_runs() -> None:
    """'music' factory creates a stub workflow."""
    # Act
    workflow = create_workflow("music")

    # Assert
    assert callable(getattr(workflow, "run", None))


def test_create_mix_workflow_runs() -> None:
    """'mix' factory creates a stub workflow."""
    # Act
    workflow = create_workflow("mix")

    # Assert
    assert callable(getattr(workflow, "run", None))
