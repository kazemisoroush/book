"""Sound effects generator for diegetic audio insertion.

Responsibilities
----------------
1. Generate sound effects via ElevenLabs Sound Effects API
2. Cache results by description hash to avoid repeated API calls
3. Return audio file paths for insertion into synthesis gaps
4. Handle API failures gracefully (log warning, return None)

Design
------
- Sound effects are requested with explicit description only (evidence-based)
- Cache directory is output_dir/sfx/
- Cache key is SHA256(description)
- If ElevenLabs API is unavailable, that SFX moment is silently skipped
  (no regression — audio still synthesises without the effect)
"""

import hashlib
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


def get_sound_effect(
    description: str,
    output_dir: Path,
    client: Any = None,
    duration_seconds: float = 2.0,
) -> Optional[Path]:
    """Generate or retrieve a cached sound effect audio file.

    Generates a sound effect via ElevenLabs Sound Effects API on first call,
    then caches the result by description hash. Subsequent calls with the
    same description return the cached file without an API call.

    Args:
        description: Natural-language description of the sound effect
            (e.g., "dry cough", "firm knock on wooden door"). Must be
            an explicit narrative mention (not hallucinated).
        output_dir: Root directory where output is stored. Sound effects
            are cached in ``output_dir/sfx/{hash}.mp3``.
        client: An ElevenLabs client instance with a ``text_to_sound_effects()``
            method. When None, returns None without error (graceful skip).
        duration_seconds: Desired duration in seconds for the generated effect.
            Default 2.0.

    Returns:
        Path to the cached MP3 file, or None if:
        - client is None (graceful skip, no error)
        - ElevenLabs API fails (logged as warning, not error)

    Notes
        - Caching is by description hash to ensure identical descriptions
          produce identical audio across the entire book (consistency).
        - API failures are logged as warnings (not errors) to allow
          audiobook synthesis to continue without the effect.
    """
    # Graceful skip if no client provided
    if client is None:
        return None

    # Compute cache key
    description_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
    cache_dir = output_dir / "sfx"
    cache_path = cache_dir / f"{description_hash}.mp3"

    # Check cache
    if cache_path.exists():
        logger.debug(
            "sound_effect_cache_hit",
            description=description,
            cache_path=str(cache_path),
        )
        return cache_path

    # Create cache directory
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(
            "sound_effect_cache_dir_create_failed",
            cache_dir=str(cache_dir),
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
        response = client.text_to_sound_effects(
            text=description,
            duration_seconds=duration_seconds,
        )
        audio_data = response.read()

        # Write to cache
        cache_path.write_bytes(audio_data)
        logger.debug(
            "sound_effect_generated_and_cached",
            description=description,
            cache_path=str(cache_path),
            size_bytes=len(audio_data),
        )
        return cache_path

    except Exception as e:
        # Graceful failure: log warning but don't raise
        # The audiobook synthesis will continue without this SFX
        logger.warning(
            "sound_effect_api_failed",
            description=description,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None
