"""Tests for workflow factory."""
import pytest

from src.workflows.workflow_factory import create_workflow


def test_create_workflow_raises_on_unknown_name() -> None:
    """create_workflow() raises ValueError for unknown workflow names."""
    with pytest.raises(ValueError, match="Unknown workflow"):
        create_workflow("unknown-workflow")


def test_create_tts_workflow_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'tts' factory raises ValueError when FISH_AUDIO_API_KEY is missing."""
    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)

    with pytest.raises(ValueError, match="FISH_AUDIO_API_KEY"):
        create_workflow("tts")
