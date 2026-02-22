"""Configuration management for the audiobook generator.

All configuration options support both CLI arguments and environment variables.
"""
import argparse
import os
import sys
from pathlib import Path
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
            crossfade_duration=float(os.getenv('CROSSFADE_DURATION')) if os.getenv('CROSSFADE_DURATION') else None,
            discover_characters_only=os.getenv('DISCOVER_CHARACTERS', 'false').lower() == 'true',
            announce_chapters=os.getenv('NO_ANNOUNCE', 'false').lower() != 'true',
            write_transcripts=os.getenv('NO_TRANSCRIPTS', 'false').lower() != 'true',
            aws=AWSConfig.from_env()
        )

    @classmethod
    def from_cli(cls, args: Optional[list[str]] = None) -> 'Config':
        """Parse configuration from CLI arguments with env var fallbacks.

        CLI arguments take precedence over environment variables.

        Args:
            args: Command line arguments to parse (defaults to sys.argv)

        Returns:
            Config instance with values from CLI args and env vars
        """
        parser = argparse.ArgumentParser(
            description="Generate full-cast audiobooks from text files"
        )

        # Input/Output
        parser.add_argument(
            "book_path",
            type=Path,
            nargs='?',  # Make optional so we can use env var fallback
            help="Path to the book file to convert (env: BOOK_PATH)"
        )

        parser.add_argument(
            "-o", "--output",
            type=Path,
            help="Output directory for audio files (default: output, env: OUTPUT_DIR)"
        )

        # TTS Provider
        parser.add_argument(
            "--provider",
            choices=["elevenlabs", "local"],
            help="TTS provider to use (default: local, env: TTS_PROVIDER)"
        )

        parser.add_argument(
            "--elevenlabs-api-key",
            type=str,
            help="ElevenLabs API key (required if using elevenlabs provider, env: ELEVENLABS_API_KEY)"
        )

        # Processing Options
        parser.add_argument(
            "--no-grouping",
            action="store_true",
            help="Disable segment grouping (env: NO_GROUPING=true)"
        )

        parser.add_argument(
            "--no-combine",
            action="store_true",
            help="Keep separate audio files instead of combining (env: NO_COMBINE=true)"
        )

        parser.add_argument(
            "--crossfade",
            type=float,
            metavar="SECONDS",
            help="Use crossfade between segments in seconds (env: CROSSFADE_DURATION)"
        )

        # Feature Flags
        parser.add_argument(
            "--discover-characters",
            action="store_true",
            help="Discover and print characters without generating audio (env: DISCOVER_CHARACTERS=true)"
        )

        parser.add_argument(
            "--no-announce",
            action="store_true",
            help="Skip chapter/preface title announcements (env: NO_ANNOUNCE=true)"
        )

        parser.add_argument(
            "--no-transcripts",
            action="store_true",
            help="Skip generating transcript text files (env: NO_TRANSCRIPTS=true)"
        )

        parsed = parser.parse_args(args)

        # Load env vars as defaults
        env_config = cls.from_env()

        # CLI args override env vars
        book_path = parsed.book_path if parsed.book_path else env_config.book_path
        output_dir = parsed.output if parsed.output else env_config.output_dir
        tts_provider = parsed.provider if parsed.provider else env_config.tts_provider
        elevenlabs_api_key = parsed.elevenlabs_api_key if parsed.elevenlabs_api_key else env_config.elevenlabs_api_key

        # Handle boolean flags (--no-X overrides env var)
        use_grouping = not parsed.no_grouping if parsed.no_grouping else env_config.use_grouping
        combine_files = not parsed.no_combine if parsed.no_combine else env_config.combine_files
        announce_chapters = not parsed.no_announce if parsed.no_announce else env_config.announce_chapters
        write_transcripts = not parsed.no_transcripts if parsed.no_transcripts else env_config.write_transcripts
        discover_characters_only = (parsed.discover_characters if parsed.discover_characters
                                    else env_config.discover_characters_only)

        crossfade_duration = parsed.crossfade if parsed.crossfade is not None else env_config.crossfade_duration

        return cls(
            book_path=book_path,
            output_dir=output_dir,
            tts_provider=tts_provider,
            elevenlabs_api_key=elevenlabs_api_key,
            use_grouping=use_grouping,
            combine_files=combine_files,
            crossfade_duration=crossfade_duration,
            discover_characters_only=discover_characters_only,
            announce_chapters=announce_chapters,
            write_transcripts=write_transcripts,
            aws=AWSConfig.from_env()
        )

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
            SystemExit: If critical errors that should stop execution
        """
        # Validate book path
        if not self.book_path or str(self.book_path) == '.':
            print("Error: book_path is required (provide via CLI argument or BOOK_PATH env var)", file=sys.stderr)
            sys.exit(1)

        if not self.book_path.exists():
            print(f"Error: Book file not found: {self.book_path}", file=sys.stderr)
            sys.exit(1)

        # Validate TTS provider
        if self.tts_provider not in ['elevenlabs', 'local']:
            print(f"Error: Invalid TTS provider: {self.tts_provider}", file=sys.stderr)
            sys.exit(1)

        if self.tts_provider == 'elevenlabs' and not self.elevenlabs_api_key:
            print("Error: --elevenlabs-api-key or ELEVENLABS_API_KEY required for elevenlabs provider",
                  file=sys.stderr)
            sys.exit(1)

        # Validate crossfade duration
        if self.crossfade_duration is not None and self.crossfade_duration < 0:
            print(f"Error: Crossfade duration must be non-negative: {self.crossfade_duration}", file=sys.stderr)
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
