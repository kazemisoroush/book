"""Tests for configuration module."""
import pytest
import tempfile
from pathlib import Path
from .config import Config, AWSConfig


class TestAWSConfig:
    """Tests for AWSConfig."""

    def test_from_env_with_custom_values(self, monkeypatch):
        """Test loading AWS config with custom environment variables."""
        # Arrange
        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        monkeypatch.setenv('AWS_BEDROCK_MODEL_ID', 'custom-model')
        monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-key')
        monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-secret')

        # Act
        config = AWSConfig.from_env()

        # Assert
        assert config.region == 'us-west-2'
        assert config.bedrock_model_id == 'custom-model'
        assert config.access_key_id == 'test-key'
        assert config.secret_access_key == 'test-secret'


class TestConfig:
    """Tests for Config."""

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

    def test_from_env_with_custom_values(self, monkeypatch, temp_book_file):
        """Test loading config from custom environment variables."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.setenv('OUTPUT_DIR', 'custom_output')
        monkeypatch.setenv('TTS_PROVIDER', 'elevenlabs')
        monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-api-key')
        monkeypatch.setenv('NO_GROUPING', 'true')
        monkeypatch.setenv('NO_COMBINE', 'true')
        monkeypatch.setenv('CROSSFADE_DURATION', '2.5')
        monkeypatch.setenv('DISCOVER_CHARACTERS', 'true')
        monkeypatch.setenv('NO_ANNOUNCE', 'true')
        monkeypatch.setenv('NO_TRANSCRIPTS', 'true')

        # Act
        config = Config.from_env()

        # Assert
        assert config.book_path == temp_book_file
        assert config.output_dir == Path('custom_output')
        assert config.tts_provider == 'elevenlabs'
        assert config.elevenlabs_api_key == 'test-api-key'
        assert config.use_grouping is False
        assert config.combine_files is False
        assert config.crossfade_duration == 2.5
        assert config.discover_characters_only is True
        assert config.announce_chapters is False
        assert config.write_transcripts is False

    def test_validate_missing_book_path(self, clean_env):
        """Test validation fails when book_path is missing."""
        # Arrange
        config = Config.from_env()

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()

    def test_validate_book_path_not_exists(self, clean_env):
        """Test validation fails when book file doesn't exist."""
        # Arrange
        config = Config.from_env()
        config.book_path = Path('/nonexistent/book.txt')

        # Act / Assert
        with pytest.raises(SystemExit):
            config.validate()

    def test_boolean_env_vars_case_insensitive(self, monkeypatch, temp_book_file):
        """Test that boolean env vars are case-insensitive."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.setenv('NO_GROUPING', 'TRUE')
        monkeypatch.setenv('NO_COMBINE', 'False')
        monkeypatch.setenv('NO_ANNOUNCE', 'true')

        # Act
        config = Config.from_env()

        # Assert
        assert config.use_grouping is False    # NO_GROUPING=TRUE means grouping disabled
        assert config.combine_files is True    # NO_COMBINE=False means combine enabled
        assert config.announce_chapters is False  # NO_ANNOUNCE=true means announce disabled

    def test_fish_audio_api_key_from_env(self, monkeypatch, temp_book_file):
        """Test that fish_audio_api_key is loaded from FISH_AUDIO_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.setenv('FISH_AUDIO_API_KEY', 'test-fish-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.fish_audio_api_key == 'test-fish-key'

    def test_fish_audio_api_key_defaults_to_none(self, monkeypatch, temp_book_file):
        """Test that fish_audio_api_key defaults to None when env var not set."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.delenv('FISH_AUDIO_API_KEY', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.fish_audio_api_key is None

    def test_stability_api_key_from_env(self, monkeypatch, temp_book_file):
        """Test that stability_api_key is loaded from STABILITY_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.setenv('STABILITY_API_KEY', 'test-stability-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.stability_api_key == 'test-stability-key'

    def test_stability_api_key_defaults_to_none(self, monkeypatch, temp_book_file):
        """Test that stability_api_key defaults to None when env var not set."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.delenv('STABILITY_API_KEY', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.stability_api_key is None

    def test_suno_api_key_from_env(self, monkeypatch, temp_book_file):
        """Test that suno_api_key is loaded from SUNO_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.setenv('SUNO_API_KEY', 'test-suno-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.suno_api_key == 'test-suno-key'

    def test_suno_api_key_defaults_to_none(self, monkeypatch, temp_book_file):
        """Test that suno_api_key defaults to None when env var not set."""
        # Arrange
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.delenv('SUNO_API_KEY', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.suno_api_key is None
