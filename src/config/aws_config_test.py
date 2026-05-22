"""Tests for AWS configuration module."""
from .aws_config import AWSConfig


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
