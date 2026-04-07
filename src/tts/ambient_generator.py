"""Generate and cache ambient background audio per scene.

Uses the ElevenLabs Sound Effects API to produce loopable ambient clips
from a natural-language description.  Results are cached in
``output_dir/ambient/{scene_id}.mp3`` so each scene's ambient is generated
at most once per output directory.

When ``scene.ambient_prompt`` is ``None`` or the API call fails, the function
returns ``None`` and logs a warning (non-fatal).
"""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.domain.models import Scene

logger = structlog.get_logger(__name__)


def get_ambient_audio(
    scene: Scene,
    output_dir: Path,
    client: Any,
    duration_seconds: float = 60.0,
) -> Optional[Path]:
    """Return path to an ambient MP3 for the given scene.

    Generates via ElevenLabs Sound Effects API using ``scene.ambient_prompt``
    on first call; caches the result in ``output_dir/ambient/{scene_id}.mp3``
    for subsequent calls.  Returns ``None`` if ``ambient_prompt`` is ``None``
    or if the API call fails (logged as warning, not error).

    Args:
        scene: The :class:`~src.domain.models.Scene` to generate ambient for.
        output_dir: Directory where the ``ambient/`` cache subfolder is created.
        client: An ElevenLabs client instance with ``text_to_sound_effects``.
        duration_seconds: Duration of the generated clip in seconds (default 60).

    Returns:
        Path to the cached ambient MP3, or ``None`` if no ambient is needed
        or generation failed.
    """
    if scene.ambient_prompt is None:
        return None

    ambient_dir = output_dir / "ambient"
    ambient_dir.mkdir(parents=True, exist_ok=True)
    cached_path = ambient_dir / f"{scene.scene_id}.mp3"

    if cached_path.exists():
        logger.debug(
            "ambient_cache_hit",
            scene_id=scene.scene_id,
            path=str(cached_path),
        )
        return cached_path

    try:
        audio_iter = client.text_to_sound_effects.convert(
            text=scene.ambient_prompt,
            duration_seconds=duration_seconds,
        )
        with open(cached_path, "wb") as f:
            for chunk in audio_iter:
                f.write(chunk)

        logger.info(
            "ambient_generated",
            scene_id=scene.scene_id,
            prompt=scene.ambient_prompt,
            duration_seconds=duration_seconds,
            path=str(cached_path),
        )
        return cached_path

    except Exception:
        logger.warning(
            "ambient_generation_failed",
            scene_id=scene.scene_id,
            prompt=scene.ambient_prompt,
            exc_info=True,
        )
        # Clean up partial file if it was created
        if cached_path.exists():
            cached_path.unlink(missing_ok=True)
        return None
