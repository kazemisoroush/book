"""Stable Audio sound effect provider implementation."""
import hashlib
import os
from pathlib import Path
from typing import Optional

import requests
import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.models import Segment

logger = structlog.get_logger(__name__)


class StableAudioSoundEffectProvider(SoundEffectProvider):
    """Stable Audio implementation of SoundEffectProvider.

    Generates sound effects via Stability AI's Stable Audio API and caches
    results by description hash to avoid redundant API calls.
    """

    def __init__(self, api_key: str, cache_dir: Path, books_dir: Path = Path("books")) -> None:
        """Initialize Stable Audio sound effect provider.

        Args:
            api_key: Stability AI API key
            cache_dir: Directory for caching generated effects
            books_dir: Base directory for book output (used by provide()).

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.cache_dir = cache_dir
        self._books_dir = books_dir
        self._segment_counter = 0

    def provide(self, segment: Segment, book_id: str) -> float:
        """Generate a sound effect for a segment.

        Args:
            segment: The segment to generate SFX for.
            book_id: The book identifier.

        Returns:
            Duration of the generated audio in seconds.
        """
        self._segment_counter += 1
        description = segment.sound_effect_detail or segment.text
        output_path = (
            self._books_dir / book_id / "audio" / "sfx"
            / f"seg_{self._segment_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        result = self.generate(description, output_path, duration_seconds=2.0)
        if result is None:
            segment.audio_path = None
            return 0.0

        duration = self._measure_duration(output_path)
        segment.audio_path = str(output_path)
        return duration

    @staticmethod
    def _measure_duration(path: Path) -> float:
        """Measure the duration of an audio file in seconds."""
        from mutagen.mp3 import MP3  # type: ignore[import-not-found]
        audio = MP3(str(path))
        return float(audio.info.length)

    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate sound effect via Stable Audio API.

        Args:
            description: Natural-language description of the sound effect
            output_path: Path where the generated audio file should be saved
            duration_seconds: Desired duration of the effect in seconds

        Returns:
            Path to generated audio file, or None on failure
        """
        # Compute cache key
        description_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{description_hash}.mp3"

        # Check cache
        if cache_path.exists():
            logger.debug(
                "stable_audio_sfx_cache_hit",
                description=description,
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
                "stable_audio_sfx_cache_dir_create_failed",
                cache_dir=str(self.cache_dir),
                error=str(e),
            )
            return None

        # Call API to generate sound effect
        try:
            logger.debug(
                "stable_audio_sfx_api_call",
                description=description,
                duration_seconds=duration_seconds,
            )

            response = requests.post(
                "https://api.stability.ai/v2beta/stable-audio/generate/audio",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "prompt": description,
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
                "stable_audio_sfx_generated_and_cached",
                description=description,
                cache_path=str(cache_path),
                size_bytes=len(audio_data),
            )

            # Copy to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            return output_path

        except requests.RequestException as e:
            logger.warning(
                "stable_audio_sfx_failed",
                description=description,
                duration_seconds=duration_seconds,
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e.response, "status_code", None) if hasattr(e, "response") else None,
            )
            return None
