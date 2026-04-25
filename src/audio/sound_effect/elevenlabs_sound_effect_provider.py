"""ElevenLabs implementation of SoundEffectProvider."""
import hashlib
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider

logger = structlog.get_logger(__name__)


class ElevenLabsSoundEffectProvider(SoundEffectProvider):
    """ElevenLabs sound effect provider using Sound Effects API.

    Generates sound effects via ElevenLabs Sound Effects API and caches
    results by description hash to avoid redundant API calls.
    """

    @property
    def name(self) -> str:
        return "elevenlabs"

    def __init__(self, client: Any, cache_dir: Path) -> None:
        """Initialize the provider.

        Args:
            client: ElevenLabs client instance with text_to_sound_effects.
            cache_dir: Directory where generated effects are cached.
        """
        self._client = client
        self._cache_dir = cache_dir

    def provide(self, segment: Any, book_id: str) -> float:
        """Not yet implemented for ElevenLabs sound effect provider."""
        raise NotImplementedError("ElevenLabsSoundEffectProvider.provide() not yet implemented")

    def _generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate a sound effect from description (internal).

        Generates via ElevenLabs Sound Effects API on first call, then caches
        the result by description hash. Subsequent calls with the same
        description return the cached file without an API call.

        Args:
            description: Natural-language description of the sound effect.
            output_path: Path where the generated audio file should be saved.
            duration_seconds: Desired duration of the effect in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        # Compute cache key, namespaced under provider name
        description_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
        cache_path = self._cache_dir / self.name / f"{description_hash}.mp3"

        # Check cache
        if cache_path.exists():
            logger.debug(
                "sound_effect_cache_hit",
                description=description,
                cache_path=str(cache_path),
            )
            # Copy from cache to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(cache_path.read_bytes())
            return output_path

        # Create cache directory (namespaced)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(
                "sound_effect_cache_dir_create_failed",
                cache_dir=str(self._cache_dir),
                error=str(e),
            )
            return None

        # Call API to generate sound effect
        try:
            logger.debug(
                "sound_effect_api_call",
                description=description,
                duration_seconds=duration_seconds,
            )
            audio_iter = self._client.text_to_sound_effects.convert(
                text=description,
                duration_seconds=duration_seconds,
            )
            audio_data = b"".join(audio_iter)

            # Write to cache
            cache_path.write_bytes(audio_data)
            logger.debug(
                "sound_effect_generated_and_cached",
                description=description,
                cache_path=str(cache_path),
                size_bytes=len(audio_data),
            )

            # Copy to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            return output_path

        except Exception as e:
            # Graceful failure: log warning but don't raise
            logger.warning(
                "sound_effect_api_failed",
                description=description,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None
