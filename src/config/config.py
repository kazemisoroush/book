"""Configuration management for the audiobook generator."""
import argparse
import os
from dataclasses import dataclass
from typing import Any, Optional

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
            suno_api_key=os.getenv('SUNO_API_KEY'),
        )

    def require_fish_audio_api_key(self) -> str:
        """Return FISH_AUDIO_API_KEY or raise if not set."""
        if not self.fish_audio_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set — configure via environment variable")
        return self.fish_audio_api_key


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


@dataclass
class CLIConfig:
    """CLI argument configuration for workflow execution.

    Parses command-line arguments and provides a clean interface
    for main.py to dispatch to workflows.
    """
    workflow: str
    url: Optional[str] = None
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    debug: bool = False
    # Feature flags
    ambient_enabled: Optional[bool] = None
    sound_effects_enabled: Optional[bool] = None
    emotion_enabled: Optional[bool] = None
    voice_design_enabled: Optional[bool] = None
    scene_context_enabled: Optional[bool] = None

    @classmethod
    def from_cli(cls) -> 'CLIConfig':
        """Parse CLI arguments and return a CLIConfig instance.

        Returns:
            CLIConfig instance with values from command-line arguments
        """
        parser = argparse.ArgumentParser(
            description="Run a book-processing workflow.",
        )
        parser.add_argument(
            "--workflow",
            choices=["parse", "ai", "tts", "ambient", "sfx", "music", "mix"],
            default="ai",
            help="Workflow to run (default: ai)",
        )
        parser.add_argument(
            "--url",
            default=None,
            help="Project Gutenberg zip URL (required for parse/ai/tts/ambient/sfx/music/mix)"
        )
        parser.add_argument(
            "--start-chapter",
            type=int,
            default=1,
            help="1-based start chapter (default: 1)"
        )
        parser.add_argument(
            "--end-chapter",
            type=int,
            default=None,
            help="1-based end chapter (inclusive)"
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            default=False,
            help="Bypass cache and re-run the workflow stage from scratch"
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            default=False,
            help="Keep individual beat MP3 files"
        )
        # Feature flags
        parser.add_argument("--enable-ambient", action="store_true", help="Enable ambient background sound")
        parser.add_argument("--disable-ambient", action="store_true", help="Disable ambient background sound")
        parser.add_argument("--enable-sound-effects", action="store_true", help="Enable sound effects")
        parser.add_argument("--disable-sound-effects", action="store_true", help="Disable sound effects")
        parser.add_argument("--enable-emotion", action="store_true", help="Enable emotion tags")
        parser.add_argument("--disable-emotion", action="store_true", help="Disable emotion tags")
        parser.add_argument("--enable-voice-design", action="store_true", help="Enable voice design")
        parser.add_argument("--disable-voice-design", action="store_true", help="Disable voice design")
        parser.add_argument("--enable-scene-context", action="store_true", help="Enable scene context")
        parser.add_argument("--disable-scene-context", action="store_true", help="Disable scene context")

        args = parser.parse_args()

        # Resolve feature flags
        def resolve_flag(enable: bool, disable: bool) -> Optional[bool]:
            if disable:
                return False
            if enable:
                return True
            return None  # Use defaults

        return cls(
            workflow=args.workflow,
            url=args.url,
            start_chapter=args.start_chapter,
            end_chapter=args.end_chapter,
            refresh=args.refresh,
            debug=args.debug,
            ambient_enabled=resolve_flag(args.enable_ambient, args.disable_ambient),
            sound_effects_enabled=resolve_flag(args.enable_sound_effects, args.disable_sound_effects),
            emotion_enabled=resolve_flag(args.enable_emotion, args.disable_emotion),
            voice_design_enabled=resolve_flag(args.enable_voice_design, args.disable_voice_design),
            scene_context_enabled=resolve_flag(args.enable_scene_context, args.disable_scene_context),
        )

    def run_kwargs(self) -> dict[str, Any]:
        """Build kwargs dict for workflow.run() from CLI config.

        Returns:
            Dict with keys suitable for splatting into workflow.run()
        """
        kwargs: dict[str, Any] = {}

        # Always include these if they're not defaults
        if self.start_chapter != 1:
            kwargs['start_chapter'] = self.start_chapter
        if self.end_chapter is not None:
            kwargs['end_chapter'] = self.end_chapter
        if self.refresh:
            kwargs['refresh'] = self.refresh
        if self.debug:
            kwargs['debug'] = self.debug

        # Include feature flags if explicitly set
        if self.ambient_enabled is not None:
            kwargs['ambient_enabled'] = self.ambient_enabled
        if self.sound_effects_enabled is not None:
            kwargs['sound_effects_enabled'] = self.sound_effects_enabled
        if self.emotion_enabled is not None:
            kwargs['emotion_enabled'] = self.emotion_enabled
        if self.voice_design_enabled is not None:
            kwargs['voice_design_enabled'] = self.voice_design_enabled
        if self.scene_context_enabled is not None:
            kwargs['scene_context_enabled'] = self.scene_context_enabled

        return kwargs
