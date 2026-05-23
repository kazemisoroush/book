"""Tests for configuration module."""
import pytest

from .config import Config


class TestConfig:
    """Tests for Config."""

    def test_provider_from_env(self, monkeypatch):
        """provider is loaded from the PROVIDER env var."""
        monkeypatch.setenv('PROVIDER', 'anthropic')

        config = Config.from_env()

        assert config.provider == 'anthropic'

    def test_provider_defaults_to_none(self, monkeypatch):
        """provider defaults to None so each axis can pick its own default."""
        monkeypatch.delenv('PROVIDER', raising=False)

        config = Config.from_env()

        assert config.provider is None

    def test_require_fish_audio_api_key_raises_when_missing(self, monkeypatch):
        """require_fish_audio_api_key raises ValueError when env var is unset."""
        monkeypatch.delenv('FISH_AUDIO_API_KEY', raising=False)
        config = Config.from_env()

        with pytest.raises(ValueError, match="FISH_AUDIO_API_KEY"):
            config.require_fish_audio_api_key()

    def test_require_fish_audio_api_key_returns_value(self, monkeypatch):
        """require_fish_audio_api_key returns the env value when set."""
        monkeypatch.setenv('FISH_AUDIO_API_KEY', 'fish-key')
        config = Config.from_env()

        assert config.require_fish_audio_api_key() == 'fish-key'

    def test_require_elevenlabs_api_key_raises_when_missing(self, monkeypatch):
        """require_elevenlabs_api_key raises ValueError when env var is unset."""
        monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
        config = Config.from_env()

        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
            config.require_elevenlabs_api_key()

    def test_require_elevenlabs_api_key_returns_value(self, monkeypatch):
        """require_elevenlabs_api_key returns the env value when set."""
        monkeypatch.setenv('ELEVENLABS_API_KEY', 'el-key')
        config = Config.from_env()

        assert config.require_elevenlabs_api_key() == 'el-key'
