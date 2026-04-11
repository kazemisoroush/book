"""Configuration management for the audiobook generator."""
import os
import sys
from pathlib import Path
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
class Config:
    """Main configuration class.

    All options support both CLI arguments and environment variables.
    CLI arguments take precedence over environment variables.
    """
    # Input/Output
    book_path: Path
    output_dir: Path

    # TTS Provider
    tts_provider: str  # "elevenlabs" or "local"
    elevenlabs_api_key: Optional[str]

    # Processing Options
    use_grouping: bool
    combine_files: bool
    crossfade_duration: Optional[float]

    # Feature Flags
    discover_characters_only: bool
    announce_chapters: bool
    write_transcripts: bool

    # AWS Configuration
    aws: AWSConfig

    # Audio Provider API Keys
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
            book_path=Path(os.getenv('BOOK_PATH', '')),
            output_dir=Path(os.getenv('OUTPUT_DIR', 'output')),
            tts_provider=os.getenv('TTS_PROVIDER', 'local'),
            elevenlabs_api_key=os.getenv('ELEVENLABS_API_KEY'),
            use_grouping=os.getenv('NO_GROUPING', 'false').lower() != 'true',
            combine_files=os.getenv('NO_COMBINE', 'false').lower() != 'true',
            crossfade_duration=float(os.getenv('CROSSFADE_DURATION', '')) if os.getenv('CROSSFADE_DURATION') else None,
            discover_characters_only=os.getenv('DISCOVER_CHARACTERS', 'false').lower() == 'true',
            announce_chapters=os.getenv('NO_ANNOUNCE', 'false').lower() != 'true',
            write_transcripts=os.getenv('NO_TRANSCRIPTS', 'false').lower() != 'true',
            aws=AWSConfig.from_env(),
            fish_audio_api_key=os.getenv('FISH_AUDIO_API_KEY'),
            stability_api_key=os.getenv('STABILITY_API_KEY'),
            suno_api_key=os.getenv('SUNO_API_KEY')
        )

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
            SystemExit: If critical errors that should stop execution
        """
        # Validate book path
        if not self.book_path or str(self.book_path) == '.':
            logger.error(
                "config_validation_error",
                reason="book_path is required",
                hint="provide via CLI argument or BOOK_PATH env var",
            )
            sys.exit(1)

        if not self.book_path.exists():
            logger.error(
                "config_validation_error",
                reason="book file not found",
                book_path=str(self.book_path),
            )
            sys.exit(1)

        # Validate TTS provider
        if self.tts_provider not in ['elevenlabs', 'local']:
            logger.error(
                "config_validation_error",
                reason="invalid TTS provider",
                tts_provider=self.tts_provider,
                valid_providers=["elevenlabs", "local"],
            )
            sys.exit(1)

        if self.tts_provider == 'elevenlabs' and not self.elevenlabs_api_key:
            logger.error(
                "config_validation_error",
                reason="ElevenLabs API key required for elevenlabs provider",
                hint="set --elevenlabs-api-key or ELEVENLABS_API_KEY",
            )
            sys.exit(1)

        # Validate crossfade duration
        if self.crossfade_duration is not None and self.crossfade_duration < 0:
            logger.error(
                "config_validation_error",
                reason="crossfade duration must be non-negative",
                crossfade_duration=self.crossfade_duration,
            )
            sys.exit(1)


# Global config instance - lazy loaded
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    This is lazy-loaded on first access and reused for subsequent calls.
    Used primarily for AWS config in existing code.
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
