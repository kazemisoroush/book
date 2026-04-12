"""Configuration management for the audiobook generator."""
import os
from typing import Optional
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AWSConfig:
    """AWS-specific configuration."""
    region: str
    bedrock_model_id: str
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'AWSConfig':
        """Load AWS configuration from environment variables."""
        return cls(
            region=os.getenv('AWS_REGION', 'us-east-1'),
            bedrock_model_id=os.getenv('AWS_BEDROCK_MODEL_ID', 'us.anthropic.claude-opus-4-6-v1'),
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )


@dataclass
class AnthropicConfig:
    """Anthropic direct API configuration."""
    api_key: Optional[str]
    model_id: str

    @classmethod
    def from_env(cls) -> 'AnthropicConfig':
        """Load Anthropic configuration from environment variables."""
        return cls(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            model_id=os.getenv('ANTHROPIC_MODEL_ID', 'claude-opus-4-5-20251101'),
        )


@dataclass
class Config:
    """Main configuration class.

    All options support environment variables.
    """
    # AWS Configuration
    aws: AWSConfig

    # Anthropic Configuration
    anthropic: AnthropicConfig

    # AI Provider selection
    ai_provider: str  # "bedrock" or "anthropic"

    # Audio Provider API Keys
    elevenlabs_api_key: Optional[str] = None
    fish_audio_api_key: Optional[str] = None
    stability_api_key: Optional[str] = None
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
            ai_provider=os.getenv('AI_PROVIDER', 'bedrock'),
            elevenlabs_api_key=os.getenv('ELEVENLABS_API_KEY'),
            fish_audio_api_key=os.getenv('FISH_AUDIO_API_KEY'),
            stability_api_key=os.getenv('STABILITY_API_KEY'),
            suno_api_key=os.getenv('SUNO_API_KEY'),
        )


# Global config instance - lazy loaded
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    This is lazy-loaded on first access and reused for subsequent calls.
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """Force reload configuration from environment.

    Useful for testing or when environment changes at runtime.
    """
    global _config
    _config = Config.from_env()
    return _config
