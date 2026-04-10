"""Fallback TTS provider wrapper."""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.tts.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)


class FallbackTTSProvider(TTSProvider):
    """TTSProvider wrapper that falls back to a secondary provider on failure.

    Tries the primary provider first. If it raises an exception matching
    fallback_on, logs a warning and tries the fallback provider. If both fail,
    re-raises the fallback's exception.
    """

    def __init__(
        self,
        primary: TTSProvider,
        fallback: TTSProvider,
        fallback_on: type[Exception] | tuple[type[Exception], ...] = Exception,
    ) -> None:
        """Initialize fallback wrapper.

        Args:
            primary: The primary TTS provider to try first
            fallback: The fallback provider to use if primary fails
            fallback_on: Exception type(s) that trigger fallback (default: all)
        """
        self.primary = primary
        self.fallback = fallback
        self.fallback_on = fallback_on

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesize text, falling back on failure.

        Args:
            All parameters are passed through to both providers.

        Returns:
            Request ID from whichever provider succeeded, or None.

        Raises:
            Exception: If both providers fail, re-raises fallback's exception.
        """
        try:
            # Try primary first
            return self.primary.synthesize(
                text=text,
                voice_id=voice_id,
                output_path=output_path,
                emotion=emotion,
                previous_text=previous_text,
                next_text=next_text,
                voice_stability=voice_stability,
                voice_style=voice_style,
                voice_speed=voice_speed,
                previous_request_ids=previous_request_ids,
            )
        except self.fallback_on as e:
            # Primary failed, try fallback
            logger.warning(
                "tts_primary_failed_falling_back_to_secondary",
                error=str(e),
                error_type=type(e).__name__,
            )

            # This may raise - let it propagate
            result = self.fallback.synthesize(
                text=text,
                voice_id=voice_id,
                output_path=output_path,
                emotion=emotion,
                previous_text=previous_text,
                next_text=next_text,
                voice_stability=voice_stability,
                voice_style=voice_style,
                voice_speed=voice_speed,
                previous_request_ids=previous_request_ids,
            )

            logger.info("tts_fallback_succeeded")
            return result

    def get_available_voices(self) -> dict[str, str]:
        """Get available voices from primary provider only.

        Returns:
            Dictionary mapping voice names to voice IDs from primary provider.
        """
        return self.primary.get_available_voices()

    def get_voices(self) -> list[dict[str, Any]]:
        """Get available voices with metadata from primary provider only.

        Returns:
            List of voice dictionaries from primary provider.
        """
        return self.primary.get_voices()
