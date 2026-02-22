"""Tests for configuration module."""
import pytest
import tempfile
from pathlib import Path
from .config import Config, AWSConfig


class TestAWSConfig:
    """Tests for AWSConfig."""

    def test_from_env_with_defaults(self, monkeypatch):
        """Test loading AWS config with default values."""
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_BEDROCK_MODEL_ID', raising=False)

        config = AWSConfig.from_env()

        assert config.region == 'us-east-1'
        assert config.bedrock_model_id == 'us.anthropic.claude-sonnet-4-20250514-v1:0'
        assert config.access_key_id is None
        assert config.secret_access_key is None

    def test_from_env_with_custom_values(self, monkeypatch):
        """Test loading AWS config with custom environment variables."""
        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        monkeypatch.setenv('AWS_BEDROCK_MODEL_ID', 'custom-model')
        monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-key')
        monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-secret')

        config = AWSConfig.from_env()

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

    def test_from_env_with_defaults(self, clean_env):
        """Test loading config from env with default values."""
        config = Config.from_env()

        assert config.book_path == Path('')
        assert config.output_dir == Path('output')
        assert config.tts_provider == 'local'
        assert config.elevenlabs_api_key is None
        assert config.use_grouping is True
        assert config.combine_files is True
        assert config.crossfade_duration is None
        assert config.discover_characters_only is False
        assert config.announce_chapters is True
        assert config.write_transcripts is True

    def test_from_env_with_custom_values(self, monkeypatch, temp_book_file):
        """Test loading config from custom environment variables."""
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

        config = Config.from_env()

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

    def test_from_cli_with_args(self, temp_book_file, clean_env):
        """Test loading config from CLI arguments."""
        args = [
            str(temp_book_file),
            '--output', 'test_output',
            '--provider', 'elevenlabs',
            '--elevenlabs-api-key', 'cli-key',
            '--no-grouping',
            '--no-combine',
            '--crossfade', '1.5',
            '--discover-characters',
            '--no-announce',
            '--no-transcripts'
        ]

        config = Config.from_cli(args)

        assert config.book_path == temp_book_file
        assert config.output_dir == Path('test_output')
        assert config.tts_provider == 'elevenlabs'
        assert config.elevenlabs_api_key == 'cli-key'
        assert config.use_grouping is False
        assert config.combine_files is False
        assert config.crossfade_duration == 1.5
        assert config.discover_characters_only is True
        assert config.announce_chapters is False
        assert config.write_transcripts is False

    def test_cli_overrides_env(self, monkeypatch, temp_book_file):
        """Test that CLI arguments override environment variables."""
        # Set env vars
        monkeypatch.setenv('OUTPUT_DIR', 'env_output')
        monkeypatch.setenv('TTS_PROVIDER', 'local')
        monkeypatch.setenv('NO_GROUPING', 'true')

        # CLI args override
        args = [
            str(temp_book_file),
            '--output', 'cli_output',
            '--provider', 'elevenlabs',
            '--elevenlabs-api-key', 'key',
            '--no-grouping'
        ]

        config = Config.from_cli(args)

        assert config.output_dir == Path('cli_output')  # CLI wins
        assert config.tts_provider == 'elevenlabs'  # CLI wins
        assert config.use_grouping is False  # CLI wins

    def test_env_used_when_cli_not_provided(self, monkeypatch, temp_book_file):
        """Test that env vars are used when CLI args not provided."""
        monkeypatch.setenv('OUTPUT_DIR', 'env_output')
        monkeypatch.setenv('TTS_PROVIDER', 'elevenlabs')
        monkeypatch.setenv('ELEVENLABS_API_KEY', 'env-key')

        args = [str(temp_book_file)]  # Only required arg

        config = Config.from_cli(args)

        assert config.output_dir == Path('env_output')  # From env
        assert config.tts_provider == 'elevenlabs'  # From env
        assert config.elevenlabs_api_key == 'env-key'  # From env

    def test_validate_missing_book_path(self, clean_env):
        """Test validation fails when book_path is missing."""
        config = Config.from_env()

        with pytest.raises(SystemExit):
            config.validate()

    def test_validate_book_path_not_exists(self, clean_env):
        """Test validation fails when book file doesn't exist."""
        config = Config.from_env()
        config.book_path = Path('/nonexistent/book.txt')

        with pytest.raises(SystemExit):
            config.validate()

    def test_validate_invalid_provider(self, temp_book_file, clean_env):
        """Test validation fails with invalid TTS provider."""
        args = [str(temp_book_file), '--provider', 'invalid']

        with pytest.raises(SystemExit):
            Config.from_cli(args)

    def test_validate_elevenlabs_missing_api_key(self, temp_book_file, clean_env):
        """Test validation fails when elevenlabs provider used without API key."""
        args = [str(temp_book_file), '--provider', 'elevenlabs']

        config = Config.from_cli(args)

        with pytest.raises(SystemExit):
            config.validate()

    def test_validate_elevenlabs_with_api_key(self, temp_book_file, clean_env):
        """Test validation passes when elevenlabs provider has API key."""
        args = [str(temp_book_file), '--provider', 'elevenlabs', '--elevenlabs-api-key', 'test-key']

        config = Config.from_cli(args)
        config.validate()  # Should not raise

        assert config.tts_provider == 'elevenlabs'
        assert config.elevenlabs_api_key == 'test-key'

    def test_validate_negative_crossfade(self, temp_book_file, clean_env):
        """Test validation fails with negative crossfade duration."""
        args = [str(temp_book_file), '--crossfade', '-1.0']

        config = Config.from_cli(args)

        with pytest.raises(SystemExit):
            config.validate()

    def test_validate_zero_crossfade(self, temp_book_file, clean_env):
        """Test validation allows zero crossfade duration (no crossfade)."""
        args = [str(temp_book_file), '--crossfade', '0']

        config = Config.from_cli(args)
        config.validate()  # Should not raise

        assert config.crossfade_duration == 0

    def test_validate_positive_crossfade(self, temp_book_file, clean_env):
        """Test validation passes with positive crossfade duration."""
        args = [str(temp_book_file), '--crossfade', '2.5']

        config = Config.from_cli(args)
        config.validate()  # Should not raise

        assert config.crossfade_duration == 2.5

    def test_boolean_env_vars_case_insensitive(self, monkeypatch, temp_book_file):
        """Test that boolean env vars are case-insensitive."""
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))
        monkeypatch.setenv('NO_GROUPING', 'TRUE')
        monkeypatch.setenv('NO_COMBINE', 'False')
        monkeypatch.setenv('NO_ANNOUNCE', 'true')

        config = Config.from_env()

        assert config.use_grouping is False  # NO_GROUPING=TRUE means grouping disabled
        assert config.combine_files is True  # NO_COMBINE=False means combine enabled
        assert config.announce_chapters is False  # NO_ANNOUNCE=true means announce disabled

    def test_from_cli_book_path_from_env(self, monkeypatch, temp_book_file):
        """Test that book_path can come from env when not in CLI args."""
        monkeypatch.setenv('BOOK_PATH', str(temp_book_file))

        args = []  # No CLI args

        config = Config.from_cli(args)

        assert config.book_path == temp_book_file

    def test_help_message(self, capsys):
        """Test that --help shows proper help message."""
        with pytest.raises(SystemExit) as exc_info:
            Config.from_cli(['--help'])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'Generate full-cast audiobooks' in captured.out
        assert 'BOOK_PATH' in captured.out  # Env var documented
