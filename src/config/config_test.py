"""Tests for configuration module."""
import pytest

from .config import Config


class TestConfig:
    """Tests for Config."""

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

    def test_reads_claude_code_oauth_token(self, monkeypatch):
        """from_env reads CLAUDE_CODE_OAUTH_TOKEN into config."""
        monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN', 'tok-123')

        config = Config.from_env()

        assert config.claude_code_oauth_token == 'tok-123'

    def test_claude_code_oauth_token_defaults_to_none(self, monkeypatch):
        """from_env leaves the token unset when the env var is absent."""
        monkeypatch.delenv('CLAUDE_CODE_OAUTH_TOKEN', raising=False)

        config = Config.from_env()

        assert config.claude_code_oauth_token is None
