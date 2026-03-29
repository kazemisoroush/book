"""Tests verifying that config.validate() uses structlog instead of print()."""
import tempfile
from pathlib import Path
import pytest

from src.config.config import Config


class TestConfigValidateUsesStructlog:
    """config.validate() must emit structlog log events instead of print()."""

    @pytest.fixture
    def temp_book_file(self):
        """Create a temporary book file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test book content")
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clear all config-related environment variables."""
        env_vars = [
            'BOOK_PATH', 'OUTPUT_DIR', 'TTS_PROVIDER', 'ELEVENLABS_API_KEY',
            'NO_GROUPING', 'NO_COMBINE', 'CROSSFADE_DURATION',
            'DISCOVER_CHARACTERS', 'NO_ANNOUNCE', 'NO_TRANSCRIPTS'
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)

    def test_validate_missing_book_path_does_not_print_to_stderr(self, clean_env, capsys):
        """validate() with missing book path must NOT print to stderr."""
        # Arrange
        config = Config.from_env()

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()
        captured = capsys.readouterr()
        assert "Error:" not in captured.err

    def test_validate_book_not_found_does_not_print_to_stderr(self, clean_env, capsys):
        """validate() with missing book file must NOT print to stderr."""
        # Arrange
        config = Config.from_env()
        config.book_path = Path('/nonexistent/book.txt')

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()
        captured = capsys.readouterr()
        assert "Error:" not in captured.err

    def test_validate_invalid_tts_provider_does_not_print_to_stderr(
        self, temp_book_file, clean_env, capsys
    ):
        """validate() with invalid tts_provider must NOT print to stderr."""
        # Arrange
        config = Config.from_env()
        config.book_path = temp_book_file
        config.tts_provider = 'invalid_provider'

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()
        captured = capsys.readouterr()
        assert "Error:" not in captured.err

    def test_validate_elevenlabs_missing_api_key_does_not_print_to_stderr(
        self, temp_book_file, clean_env, capsys
    ):
        """validate() with elevenlabs but no API key must NOT print to stderr."""
        # Arrange
        config = Config.from_env()
        config.book_path = temp_book_file
        config.tts_provider = 'elevenlabs'
        config.elevenlabs_api_key = None

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()
        captured = capsys.readouterr()
        assert "Error:" not in captured.err

    def test_validate_negative_crossfade_does_not_print_to_stderr(
        self, temp_book_file, clean_env, capsys
    ):
        """validate() with negative crossfade must NOT print to stderr."""
        # Arrange
        config = Config.from_env()
        config.book_path = temp_book_file
        config.crossfade_duration = -1.0

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()
        captured = capsys.readouterr()
        assert "Error:" not in captured.err

    def test_validate_still_calls_sys_exit(self, clean_env):
        """validate() must still call sys.exit(1) on error after switching to structlog."""
        # Arrange
        config = Config.from_env()

        # Act / Assert
        with pytest.raises(SystemExit) as exc_info:
            config.validate()
        assert exc_info.value.code == 1
