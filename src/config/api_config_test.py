"""Tests for the API server configuration."""
from src.config.api_config import ApiConfig


def test_from_env_uses_defaults_when_unset(monkeypatch):
    # Arrange
    monkeypatch.delenv("API_HOST", raising=False)
    monkeypatch.delenv("API_PORT", raising=False)

    # Act
    config = ApiConfig.from_env()

    # Assert
    assert config.host == "127.0.0.1"
    assert config.port == 8000


def test_from_env_reads_overrides(monkeypatch):
    # Arrange
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9001")

    # Act
    config = ApiConfig.from_env()

    # Assert
    assert config.host == "0.0.0.0"
    assert config.port == 9001
