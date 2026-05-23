"""Configuration management for the audiobook generator."""
import os
from dataclasses import dataclass
from typing import Optional

from src.config.anthropic_config import AnthropicConfig
from src.config.aws_config import AWSConfig


@dataclass
class Config:
    """Main configuration class.

    All options support environment variables.
    """
    # AWS Configuration
    aws: AWSConfig

    # Anthropic Configuration
    anthropic: AnthropicConfig

    # Unified provider selection across all axes (ai, tts, ambient, sfx).
    # Each axis interprets the value independently; unrecognized values
    # fall through to that axis' default.
    provider: Optional[str] = None

    # Audio Provider API Keys
    elevenlabs_api_key: Optional[str] = None
    fish_audio_api_key: Optional[str] = None
    suno_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'Config':
        """Load all configuration from environment variables only.

        Returns:
            Config instance with values from environment variables
        """
        return cls(
            aws=AWSConfig.from_env(),
            anthropic=AnthropicConfig.from_env(),
            provider=os.getenv('PROVIDER'),
            elevenlabs_api_key=os.getenv('ELEVENLABS_API_KEY'),
            fish_audio_api_key=os.getenv('FISH_AUDIO_API_KEY'),
            suno_api_key=os.getenv('SUNO_API_KEY'),
        )

    def require_fish_audio_api_key(self) -> str:
        """Return FISH_AUDIO_API_KEY or raise if not set."""
        if not self.fish_audio_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set; configure via environment variable")
        return self.fish_audio_api_key

    def require_elevenlabs_api_key(self) -> str:
        """Return ELEVENLABS_API_KEY or raise if not set."""
        if not self.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY not set; configure via environment variable")
        return self.elevenlabs_api_key
