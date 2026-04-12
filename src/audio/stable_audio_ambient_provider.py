"""Stable Audio ambient provider implementation."""
import hashlib
from pathlib import Path
from typing import Optional

import requests
import structlog

from src.audio.ambient_provider import AmbientProvider

logger = structlog.get_logger(__name__)


class StableAudioAmbientProvider(AmbientProvider):
    """Stable Audio implementation of AmbientProvider.

    Generates ambient audio via Stability AI's Stable Audio API and caches
    results by prompt hash to avoid redundant API calls.
    """

    def __init__(self, api_key: str, cache_dir: Path) -> None:
        """Initialize Stable Audio ambient provider.

        Args:
            api_key: Stability AI API key
            cache_dir: Directory for caching generated ambient tracks

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.cache_dir = cache_dir

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate ambient audio via Stable Audio API.

        Args:
            prompt: Natural-language description of the ambient environment
            output_path: Path where the generated audio file should be saved
            duration_seconds: Desired duration of the ambient clip in seconds

        Returns:
            Path to generated audio file, or None on failure
        """
        # Compute cache key
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{prompt_hash}.mp3"

        # Check cache
        if cache_path.exists():
            logger.debug(
                "stable_audio_ambient_cache_hit",
                prompt=prompt,
                cache_path=str(cache_path),
            )
            # Copy from cache to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(cache_path.read_bytes())
            return output_path

        # Create cache directory
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(
                "stable_audio_ambient_cache_dir_create_failed",
                cache_dir=str(self.cache_dir),
                error=str(e),
            )
            return None

        # Call API to generate ambient audio
        try:
            logger.debug(
                "stable_audio_ambient_api_call",
                prompt=prompt,
                duration_seconds=duration_seconds,
            )

            response = requests.post(
                "https://api.stability.ai/v2beta/stable-audio/generate/audio",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "prompt": prompt,
                    "duration": duration_seconds,
                    "output_format": "mp3",
                },
                timeout=60,
            )
            response.raise_for_status()

            audio_data = response.content

            # Write to cache
            cache_path.write_bytes(audio_data)
            logger.debug(
                "stable_audio_ambient_generated_and_cached",
                prompt=prompt,
                cache_path=str(cache_path),
                size_bytes=len(audio_data),
            )

            # Copy to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            return output_path

        except requests.RequestException as e:
            logger.warning(
                "stable_audio_ambient_failed",
                prompt=prompt,
                duration_seconds=duration_seconds,
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e.response, "status_code", None) if hasattr(e, "response") else None,
            )
            return None
