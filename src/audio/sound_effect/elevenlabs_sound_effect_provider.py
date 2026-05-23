"""ElevenLabs implementation of SoundEffectProvider."""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.beat import Beat

logger = structlog.get_logger(__name__)


def _audio_duration_seconds(path: Path) -> float:
    """Return MP3 duration in seconds via mutagen."""
    from mutagen.mp3 import MP3  # type: ignore[import-not-found]
    return float(MP3(str(path)).info.length)


class ElevenLabsSoundEffectProvider(SoundEffectProvider):
    """ElevenLabs sound effect provider using the Sound Effects API.

    Generates one MP3 per SFX beat and caches by file existence. Output is
    written to ``books_dir/<book_id>/audio/sfx/elevenlabs/beat_NNNN.mp3``
    with the counter scoped per provider instance (one workflow run = one
    counter sequence).
    """

    @property
    def name(self) -> str:
        return "elevenlabs"

    def __init__(self, client: Any, books_dir: Path) -> None:
        """Initialize the provider.

        Args:
            client: ElevenLabs client instance with text_to_sound_effects.
            books_dir: Base directory for book output (per-book outputs live
                under ``books_dir/<book_id>/audio/sfx/<provider>/``).
        """
        self._client = client
        self._books_dir = books_dir
        self._beat_counter = 0

    def provide(self, beat: Beat, book_id: str) -> float:
        description = beat.sound_effect_detail or beat.text
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "sfx" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        result = self._generate(description, output_path)
        if result is None:
            return 0.0
        beat.audio_path = str(result)
        return _audio_duration_seconds(result)

    def _generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate a sound effect, skipping the API call if the file exists.

        Args:
            description: Natural-language description of the sound effect.
            output_path: Destination file path. Existence acts as the cache.
            duration_seconds: Desired duration of the effect in seconds.

        Returns:
            Path to the generated audio file, or None on failure.
        """
        if output_path.exists():
            logger.debug("sound_effect_cache_hit", output_path=str(output_path))
            return output_path

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

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            logger.debug(
                "sound_effect_generated",
                description=description,
                output_path=str(output_path),
                size_bytes=len(audio_data),
            )
            return output_path

        except Exception as e:
            logger.warning(
                "sound_effect_api_failed",
                description=description,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None
