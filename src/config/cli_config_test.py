"""Tests for CLI configuration module."""
import pytest

from .cli_config import CLIConfig


class TestCLIConfig:
    """Tests for CLIConfig."""

    def test_from_cli_parses_workflow_argument(self, monkeypatch):
        """Test that workflow name is parsed from CLI."""
        # Arrange
        monkeypatch.setattr('sys.argv', ['prog', '--workflow', 'tts', '--url', 'http://example.com'])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.workflow == 'tts'

    def test_from_cli_parses_url_argument(self, monkeypatch):
        """Test that URL is parsed from CLI."""
        # Arrange
        test_url = 'https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip'
        monkeypatch.setattr('sys.argv', ['prog', '--workflow', 'ai', '--url', test_url])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.url == test_url

    def test_from_cli_parses_chapter_range(self, monkeypatch):
        """Test that start-chapter and end-chapter are parsed."""
        # Arrange
        monkeypatch.setattr('sys.argv', [
            'prog', '--workflow', 'ai', '--url', 'http://example.com',
            '--start-chapter', '5', '--end-chapter', '15'
        ])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.start_chapter == 5
        assert config.end_chapter == 15

    def test_from_cli_parses_refresh_flag(self, monkeypatch):
        """Test that --refresh is parsed as boolean."""
        # Arrange
        monkeypatch.setattr('sys.argv', [
            'prog', '--workflow', 'ai', '--url', 'http://example.com', '--refresh'
        ])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.refresh is True

    def test_from_cli_parses_debug_flag(self, monkeypatch):
        """Test that --debug is parsed as boolean."""
        # Arrange
        monkeypatch.setattr('sys.argv', [
            'prog', '--workflow', 'tts', '--url', 'http://example.com', '--debug'
        ])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.debug is True

    def test_from_cli_defaults_workflow_to_ai(self, monkeypatch):
        """Test that workflow defaults to 'ai' when not specified."""
        # Arrange
        monkeypatch.setattr('sys.argv', ['prog', '--url', 'http://example.com'])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.workflow == 'ai'

    def test_from_cli_raises_when_url_missing(self, monkeypatch):
        """Test that from_cli() raises ValueError when --url is not provided."""
        # Arrange
        monkeypatch.setattr('sys.argv', ['prog', '--workflow', 'ai'])

        # Act / Assert
        with pytest.raises(ValueError, match=r"--url is required for --workflow ai"):
            CLIConfig.from_cli()

    def test_validate_raises_when_url_is_none(self):
        """Test that validate() raises ValueError when url is None."""
        # Arrange
        config = CLIConfig(workflow='tts', url=None)

        # Act / Assert
        with pytest.raises(ValueError, match=r"--url is required for --workflow tts"):
            config.validate()

    def test_validate_passes_when_url_is_set(self):
        """Test that validate() succeeds when url is provided."""
        # Arrange
        config = CLIConfig(workflow='ai', url='http://example.com')

        # Act / Assert (no exception)
        config.validate()
