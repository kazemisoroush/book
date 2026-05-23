"""ElevenLabs implementation of AmbientProvider."""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.ambient.ambient_provider import AmbientProvider
from src.domain.models import Scene

logger = structlog.get_logger(__name__)


def _audio_duration_seconds(path: Path) -> float:
    """Return MP3 duration in seconds via mutagen."""
    from mutagen.mp3 import MP3  # type: ignore[import-not-found]
    return float(MP3(str(path)).info.length)


class ElevenLabsAmbientProvider(AmbientProvider):
    """ElevenLabs ambient provider using the Sound Effects API.

    Generates ambient audio with ``loop=True`` and caches by the output file's
    existence on disk. Output is written to
    ``books_dir/<book_id>/audio/ambient/elevenlabs/<scene.scene_id>.mp3``.
    """

    @property
    def name(self) -> str:
        return "elevenlabs"

    def __init__(self, client: Any, books_dir: Path) -> None:
        """Initialize the provider.

        Args:
            client: ElevenLabs client instance with text_to_sound_effects.
            books_dir: Base directory for book output (per-book outputs live
                under ``books_dir/<book_id>/audio/ambient/<provider>/``).
        """
        self._client = client
        self._books_dir = books_dir

    def provide(self, scene: Scene, book_id: str) -> float:
        if scene.ambient_prompt is None:
            raise ValueError(
                f"Scene {scene.scene_id!r} has no ambient_prompt set"
            )
        output_path = (
            self._books_dir / book_id / "audio" / "ambient" / self.name
            / f"{scene.scene_id}.mp3"
        )
        result = self._generate(scene.ambient_prompt, output_path)
        if result is None:
            return 0.0
        return _audio_duration_seconds(result)

    def _generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate ambient audio, skipping the API call if the file exists.

        Args:
            prompt: Natural-language description of the ambient environment.
            output_path: Destination file path. Existence acts as the cache.
            duration_seconds: Desired duration of the ambient clip in seconds.

        Returns:
            Path to the generated audio file, or None on failure.
        """
        if output_path.exists():
            logger.debug("ambient_cache_hit", output_path=str(output_path))
            return output_path

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

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            logger.info(
                "ambient_generated",
                prompt=prompt,
                output_path=str(output_path),
                size_bytes=len(audio_data),
            )
            return output_path

        except Exception as e:
            logger.warning(
                "ambient_api_failed",
                prompt=prompt,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None
