"""Tests for configuration module."""
from .config import AWSConfig, CLIConfig, Config


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

    def test_from_env_loads_ai_provider(self, monkeypatch):
        """Test that ai_provider is loaded from AI_PROVIDER env var."""
        # Arrange
        monkeypatch.setenv('AI_PROVIDER', 'anthropic')

        # Act
        config = Config.from_env()

        # Assert
        assert config.ai_provider == 'anthropic'

    def test_ai_provider_defaults_to_bedrock(self, monkeypatch):
        """Test that ai_provider defaults to 'bedrock' when not set."""
        # Arrange
        monkeypatch.delenv('AI_PROVIDER', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.ai_provider == 'bedrock'

    def test_fish_audio_api_key_from_env(self, monkeypatch):
        """Test that fish_audio_api_key is loaded from FISH_AUDIO_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('FISH_AUDIO_API_KEY', 'test-fish-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.fish_audio_api_key == 'test-fish-key'

    def test_fish_audio_api_key_defaults_to_none(self, monkeypatch):
        """Test that fish_audio_api_key defaults to None when env var not set."""
        # Arrange
        monkeypatch.delenv('FISH_AUDIO_API_KEY', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.fish_audio_api_key is None

    def test_suno_api_key_from_env(self, monkeypatch):
        """Test that suno_api_key is loaded from SUNO_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('SUNO_API_KEY', 'test-suno-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.suno_api_key == 'test-suno-key'

    def test_suno_api_key_defaults_to_none(self, monkeypatch):
        """Test that suno_api_key defaults to None when env var not set."""
        # Arrange
        monkeypatch.delenv('SUNO_API_KEY', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.suno_api_key is None

    def test_elevenlabs_api_key_from_env(self, monkeypatch):
        """Test that elevenlabs_api_key is loaded from ELEVENLABS_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-el-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.elevenlabs_api_key == 'test-el-key'


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

    def test_run_kwargs_returns_dict_with_workflow_params(self, monkeypatch):
        """Test that run_kwargs() builds the correct dict for workflow.run()."""
        # Arrange
        monkeypatch.setattr('sys.argv', [
            'prog', '--workflow', 'ai', '--url', 'http://example.com',
            '--start-chapter', '2', '--end-chapter', '10', '--refresh', '--debug'
        ])
        config = CLIConfig.from_cli()

        # Act
        kwargs = config.run_kwargs()

        # Assert
        assert kwargs['start_chapter'] == 2
        assert kwargs['end_chapter'] == 10
        assert kwargs['refresh'] is True
        assert kwargs['debug'] is True

    def test_from_cli_defaults_workflow_to_ai(self, monkeypatch):
        """Test that workflow defaults to 'ai' when not specified."""
        # Arrange
        monkeypatch.setattr('sys.argv', ['prog', '--url', 'http://example.com'])

        # Act
        config = CLIConfig.from_cli()

        # Assert
        assert config.workflow == 'ai'
