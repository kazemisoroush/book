"""Configuration management for the audiobook generator.

This module handles all configuration from environment variables and provides
type-safe access to configuration values.
"""
import os
from typing import Optional
from dataclasses import dataclass


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
            bedrock_model_id=os.getenv('AWS_BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0'),
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )


@dataclass
class Config:
    """Main configuration class."""
    aws: AWSConfig

    @classmethod
    def from_env(cls) -> 'Config':
        """Load all configuration from environment variables."""
        return cls(
            aws=AWSConfig.from_env()
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
