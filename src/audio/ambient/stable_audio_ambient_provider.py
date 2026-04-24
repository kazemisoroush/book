"""Stable Audio ambient provider implementation."""
import hashlib
import os
from pathlib import Path
from typing import Optional

import requests
import structlog

from src.audio.ambient.ambient_provider import AmbientProvider
from src.domain.models import Scene

logger = structlog.get_logger(__name__)


class StableAudioAmbientProvider(AmbientProvider):
    """Stable Audio implementation of AmbientProvider.

    Generates ambient audio via Stability AI's Stable Audio API and caches
    results by prompt hash to avoid redundant API calls.
    """

    def __init__(self, api_key: str, books_dir: Path = Path("books")) -> None:
        """Initialize Stable Audio ambient provider.

        Args:
            api_key: Stability AI API key
            books_dir: Base directory for book output. Cache lives at
                       ``books_dir / "cache" / "ambient"``.

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.cache_dir = books_dir / "cache" / "ambient"
        self._books_dir = books_dir

    def provide(self, scene: Scene, book_id: str) -> float:
        """Generate ambient audio for a scene.

        Args:
            scene: The scene to generate ambient audio for.
            book_id: The book identifier.

        Returns:
            Duration of the generated audio in seconds.
        """
        if scene.ambient_prompt is None:
            return 0.0

        output_path = (
            self._books_dir / book_id / "audio" / "ambient"
            / f"{scene.scene_id}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        result = self.generate(scene.ambient_prompt, output_path)
        if result is None:
            return 0.0

        duration = self._measure_duration(output_path)
        return duration

    @staticmethod
    def _measure_duration(path: Path) -> float:
        """Measure the duration of an audio file in seconds."""
        from mutagen.mp3 import MP3  # type: ignore[import-not-found]
        audio = MP3(str(path))
        return float(audio.info.length)

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
