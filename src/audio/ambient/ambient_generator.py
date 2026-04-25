"""Generate and cache ambient background audio per scene.

Backward compatibility wrapper around ElevenLabsAmbientProvider.

Uses the ElevenLabs Sound Effects API to produce loopable ambient clips
from a natural-language description.  Results are cached in
``output_dir/ambient/{scene_id}.mp3`` so each scene's ambient is generated
at most once per output directory.

When ``scene.ambient_prompt`` is ``None`` or the API call fails, the function
returns ``None`` and logs a warning (non-fatal).
"""
from pathlib import Path
from typing import Any, Optional

from src.audio.ambient.elevenlabs_ambient_provider import ElevenLabsAmbientProvider
from src.domain.models import Scene


def get_ambient_audio(
    scene: Scene,
    output_dir: Path,
    client: Any,
    duration_seconds: float = 30.0,
) -> Optional[Path]:
    """Return path to an ambient MP3 for the given scene.

    Backward compatibility wrapper around ElevenLabsAmbientProvider.
    Generates via ElevenLabs Sound Effects API using ``scene.ambient_prompt``
    on first call; caches the result in ``output_dir/ambient/{scene_id}.mp3``
    for subsequent calls.  Returns ``None`` if ``ambient_prompt`` is ``None``
    or if the API call fails (logged as warning, not error).

    Args:
        scene: The :class:`~src.domain.models.Scene` to generate ambient for.
        output_dir: Directory where the ``ambient/`` cache subfolder is created.
        client: An ElevenLabs client instance with ``text_to_sound_effects``.
        duration_seconds: Duration of the generated clip in seconds (default 30).

    Returns:
        Path to the cached ambient MP3, or ``None`` if no ambient is needed
        or generation failed.
    """
    if scene.ambient_prompt is None:
        return None

    # Delegate to provider
    ambient_dir = output_dir / "ambient"
    provider = ElevenLabsAmbientProvider(client, ambient_dir)

    # Output path uses scene_id as filename
    output_path = ambient_dir / f"{scene.scene_id}.mp3"

    return provider._generate(scene.ambient_prompt, output_path, duration_seconds)
