"""Tests for configuration module."""
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

    def test_stability_api_key_from_env(self, monkeypatch):
        """Test that stability_api_key is loaded from STABILITY_API_KEY env var."""
        # Arrange
        monkeypatch.setenv('STABILITY_API_KEY', 'test-stability-key')

        # Act
        config = Config.from_env()

        # Assert
        assert config.stability_api_key == 'test-stability-key'

    def test_stability_api_key_defaults_to_none(self, monkeypatch):
        """Test that stability_api_key defaults to None when env var not set."""
        # Arrange
        monkeypatch.delenv('STABILITY_API_KEY', raising=False)

        # Act
        config = Config.from_env()

        # Assert
        assert config.stability_api_key is None

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
