"""Sound effects generator for diegetic audio insertion.

Backward compatibility wrapper around ElevenLabsSoundEffectProvider.

Responsibilities
----------------
1. Provide backward-compatible API for existing callers
2. Delegate to ElevenLabsSoundEffectProvider internally
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

from src.tts.elevenlabs_sound_effect_provider import ElevenLabsSoundEffectProvider


def get_sound_effect(
    description: str,
    output_dir: Path,
    client: Any = None,
    duration_seconds: float = 2.0,
) -> Optional[Path]:
    """Generate or retrieve a cached sound effect audio file.

    Backward compatibility wrapper around ElevenLabsSoundEffectProvider.
    Generates a sound effect via ElevenLabs Sound Effects API on first call,
    then caches the result by description hash. Subsequent calls with the
    same description return the cached file without an API call.

    Args:
        description: Natural-language description of the sound effect
            (e.g., "dry cough", "firm knock on wooden door"). Must be
            an explicit narrative mention (not hallucinated).
        output_dir: Root directory where output is stored. Sound effects
            are cached in ``output_dir/sfx/{hash}.mp3``.
        client: An ElevenLabs client instance with a
            ``text_to_sound_effects.convert()`` method. When None, returns None
            without error (graceful skip).
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

    # Delegate to provider
    cache_dir = output_dir / "sfx"
    provider = ElevenLabsSoundEffectProvider(client, cache_dir)

    # Compute output path using same hash logic
    description_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
    output_path = cache_dir / f"{description_hash}.mp3"

    return provider.generate(description, output_path, duration_seconds)
