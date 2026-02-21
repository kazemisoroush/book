"""Tests for configuration module."""
import os
import pytest
from .config import Config, AWSConfig, get_config, reload_config


class TestAWSConfig:
    """Tests for AWSConfig."""

    def test_from_env_with_defaults(self, monkeypatch):
        """Test loading AWS config with default values."""
        # Clear AWS env vars
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_BEDROCK_MODEL_ID', raising=False)
        monkeypatch.delenv('AWS_ACCESS_KEY_ID', raising=False)
        monkeypatch.delenv('AWS_SECRET_ACCESS_KEY', raising=False)

        config = AWSConfig.from_env()

        assert config.region == 'us-east-1'
        assert config.bedrock_model_id == 'us.anthropic.claude-sonnet-4-20250514-v1:0'
        assert config.access_key_id is None
        assert config.secret_access_key is None

    def test_from_env_with_custom_values(self, monkeypatch):
        """Test loading AWS config with custom environment values."""
        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        monkeypatch.setenv('AWS_BEDROCK_MODEL_ID', 'custom-model-id')
        monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-key-id')
        monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-secret')
        monkeypatch.setenv('AWS_SESSION_TOKEN', 'test-token')

        config = AWSConfig.from_env()

        assert config.region == 'us-west-2'
        assert config.bedrock_model_id == 'custom-model-id'
        assert config.access_key_id == 'test-key-id'
        assert config.secret_access_key == 'test-secret'
        assert config.session_token == 'test-token'


class TestConfig:
    """Tests for main Config class."""

    def test_from_env(self, monkeypatch):
        """Test loading full config from environment."""
        monkeypatch.setenv('AWS_REGION', 'eu-west-1')

        config = Config.from_env()

        assert isinstance(config.aws, AWSConfig)
        assert config.aws.region == 'eu-west-1'

    def test_get_config_singleton(self, monkeypatch):
        """Test that get_config returns the same instance."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')
        reload_config()  # Reset global state

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_reload_config(self, monkeypatch):
        """Test that reload_config creates a new instance."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')
        reload_config()

        config1 = get_config()

        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        config2 = reload_config()

        assert config1 is not config2
        assert config1.aws.region == 'us-east-1'
        assert config2.aws.region == 'us-west-2'
