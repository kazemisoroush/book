"""Tests for workflow factory."""
import pytest
from .workflow_factory import create_workflow
from .project_gutenberg_workflow import ProjectGutenbergWorkflow
from .ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from .tts_workflow import TTSWorkflow
from .ambient_workflow import AmbientWorkflow
from .sfx_workflow import SfxWorkflow
from .music_workflow import MusicWorkflow
from .mix_workflow import MixWorkflow
from src.config.config import reload_config


class TestCreateWorkflow:
    """Tests for create_workflow function."""

    def test_create_workflow_returns_parse_workflow(self):
        """Test that 'parse' returns ProjectGutenbergWorkflow."""
        # Act
        workflow = create_workflow('parse')

        # Assert
        assert isinstance(workflow, ProjectGutenbergWorkflow)

    def test_create_workflow_returns_ai_workflow(self):
        """Test that 'ai' returns AIProjectGutenbergWorkflow."""
        # Act
        workflow = create_workflow('ai')

        # Assert
        assert isinstance(workflow, AIProjectGutenbergWorkflow)

    def test_create_workflow_returns_tts_workflow(self, monkeypatch):
        """Test that 'tts' returns TTSWorkflow."""
        # Arrange - mock the API key requirement
        monkeypatch.setenv('FISH_AUDIO_API_KEY', 'test-key')
        reload_config()

        # Act
        workflow = create_workflow('tts')

        # Assert
        assert isinstance(workflow, TTSWorkflow)

    def test_create_workflow_returns_ambient_workflow(self, monkeypatch):
        """Test that 'ambient' returns AmbientWorkflow."""
        # Arrange - mock the API key requirement
        monkeypatch.setenv('STABILITY_API_KEY', 'test-key')
        reload_config()

        # Act
        workflow = create_workflow('ambient')

        # Assert
        assert isinstance(workflow, AmbientWorkflow)

    def test_create_workflow_returns_sfx_workflow(self, monkeypatch):
        """Test that 'sfx' returns SfxWorkflow."""
        # Arrange - mock the API key requirement
        monkeypatch.setenv('STABILITY_API_KEY', 'test-key')
        reload_config()

        # Act
        workflow = create_workflow('sfx')

        # Assert
        assert isinstance(workflow, SfxWorkflow)

    def test_create_workflow_returns_music_workflow(self, monkeypatch):
        """Test that 'music' returns MusicWorkflow."""
        # Arrange - mock the API key requirement
        monkeypatch.setenv('SUNO_API_KEY', 'test-key')
        reload_config()

        # Act
        workflow = create_workflow('music')

        # Assert
        assert isinstance(workflow, MusicWorkflow)

    def test_create_workflow_returns_mix_workflow(self):
        """Test that 'mix' returns MixWorkflow."""
        # Act
        workflow = create_workflow('mix')

        # Assert
        assert isinstance(workflow, MixWorkflow)

    def test_create_workflow_raises_on_unknown_workflow(self):
        """Test that unknown workflow name raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown workflow"):
            create_workflow('unknown-workflow')
