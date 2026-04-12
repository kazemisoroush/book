"""ElevenLabs implementation of AmbientProvider."""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.ambient.ambient_provider import AmbientProvider

logger = structlog.get_logger(__name__)


class ElevenLabsAmbientProvider(AmbientProvider):
    """ElevenLabs ambient provider using Sound Effects API.

    Generates ambient audio via ElevenLabs Sound Effects API with loop=True
    and caches results by output path (scene ID) to avoid redundant API calls.
    """

    def __init__(self, client: Any, cache_dir: Path) -> None:
        """Initialize the provider.

        Args:
            client: ElevenLabs client instance with text_to_sound_effects.
            cache_dir: Directory where generated ambient audio is cached.
        """
        self._client = client
        self._cache_dir = cache_dir

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate ambient audio from natural-language prompt.

        Generates via ElevenLabs Sound Effects API with loop=True on first call,
        then caches the result by output_path name. Subsequent calls with the
        same output_path return the cached file without an API call.

        Args:
            prompt: Natural-language description of the ambient environment.
            output_path: Path where the generated audio file should be saved.
            duration_seconds: Desired duration of the ambient clip in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        # Use output_path name as cache key (typically scene_id.mp3)
        cache_path = self._cache_dir / output_path.name

        # Check cache
        if cache_path.exists():
            logger.debug(
                "ambient_cache_hit",
                prompt=prompt,
                cache_path=str(cache_path),
            )
            # Copy from cache to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(cache_path.read_bytes())
            return output_path

        # Create cache directory
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(
                "ambient_cache_dir_create_failed",
                cache_dir=str(self._cache_dir),
                error=str(e),
            )
            return None

        # Call API to generate ambient audio
        try:
            logger.debug(
                "ambient_api_call",
                prompt=prompt,
                duration_seconds=duration_seconds,
            )
            audio_iter = self._client.text_to_sound_effects.convert(
                text=prompt,
                duration_seconds=duration_seconds,
                loop=True,
            )
            audio_data = b"".join(audio_iter)

            # Write to cache
            cache_path.write_bytes(audio_data)
            logger.info(
                "ambient_generated_and_cached",
                prompt=prompt,
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
                "ambient_api_failed",
                prompt=prompt,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Clean up partial file if it was created
            if cache_path.exists():
                cache_path.unlink(missing_ok=True)
            return None
