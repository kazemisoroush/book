"""Suno AI music provider implementation."""
import hashlib
import time
from pathlib import Path
from typing import Optional

import requests
import structlog

from src.tts.music_provider import MusicProvider

logger = structlog.get_logger(__name__)


class SunoMusicProvider(MusicProvider):
    """Suno AI implementation of MusicProvider.

    Generates music via Suno AI's async generation API with polling.
    Caches results by prompt hash to avoid redundant API calls.
    """

    def __init__(
        self,
        api_key: str,
        cache_dir: Path,
        base_url: str = "https://api.suno.ai",
    ) -> None:
        """Initialize Suno music provider.

        Args:
            api_key: Suno AI API key
            cache_dir: Directory for caching generated music tracks
            base_url: Suno API base URL (default production endpoint)

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.cache_dir = cache_dir
        self.base_url = base_url
        self._timeout = 120  # seconds
        self._poll_interval = 5  # seconds

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate music via Suno AI API.

        Args:
            prompt: Natural-language description of desired music mood/style
            output_path: Path where the generated audio file should be saved
            duration_seconds: Desired duration of the music track in seconds

        Returns:
            Path to generated audio file, or None on failure/timeout
        """
        # Compute cache key
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{prompt_hash}.mp3"

        # Check cache
        if cache_path.exists():
            logger.debug(
                "suno_music_cache_hit",
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
                "suno_music_cache_dir_create_failed",
                cache_dir=str(self.cache_dir),
                error=str(e),
            )
            return None

        # Submit generation request
        try:
            logger.debug(
                "suno_music_submit",
                prompt=prompt,
                duration_seconds=duration_seconds,
            )

            submit_response = requests.post(
                f"{self.base_url}/api/generate",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "prompt": prompt,
                    "duration": duration_seconds,
                    "model": "chirp-v3",
                    "instrumental": False,
                },
                timeout=30,
            )
            submit_response.raise_for_status()

            task_id = submit_response.json()["id"]

            logger.debug(
                "suno_music_task_submitted",
                task_id=task_id,
                prompt=prompt,
            )

        except requests.RequestException as e:
            logger.warning(
                "suno_music_generation_failed",
                prompt=prompt,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < self._timeout:
            try:
                poll_response = requests.get(
                    f"{self.base_url}/api/task/{task_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30,
                )
                poll_response.raise_for_status()

                status_data = poll_response.json()
                status = status_data.get("status")

                if status == "complete":
                    # Download audio
                    try:
                        download_response = requests.get(
                            f"{self.base_url}/api/download/{task_id}",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            timeout=60,
                        )
                        download_response.raise_for_status()

                        audio_data = download_response.content

                        # Write to cache
                        cache_path.write_bytes(audio_data)

                        logger.info(
                            "suno_music_generated",
                            prompt=prompt,
                            duration_seconds=duration_seconds,
                            task_id=task_id,
                            cache_path=str(cache_path),
                        )

                        # Copy to output_path
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(audio_data)
                        return output_path

                    except requests.RequestException as e:
                        logger.warning(
                            "suno_music_download_failed",
                            task_id=task_id,
                            error=str(e),
                        )
                        return None

                elif status == "failed":
                    logger.warning(
                        "suno_music_task_failed",
                        task_id=task_id,
                        prompt=prompt,
                    )
                    return None

                # Still processing, wait and poll again
                time.sleep(self._poll_interval)

            except requests.RequestException as e:
                logger.warning(
                    "suno_music_poll_failed",
                    task_id=task_id,
                    error=str(e),
                )
                # Continue polling despite error
                time.sleep(self._poll_interval)

        # Timeout reached
        logger.warning(
            "suno_music_timeout",
            task_id=task_id,
            prompt=prompt,
            timeout_seconds=self._timeout,
        )
        return None
