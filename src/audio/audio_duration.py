"""Shared audio duration helper used across all audio providers."""
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def get_audio_duration(path: Path) -> float:
    """Return the duration in seconds of the audio file at *path* via ffprobe.

    Works for any container/codec ffprobe understands (mp3, wav, ogg, etc.).
    Falls back to ``0.0`` if ffprobe is unavailable or the file cannot be read.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        logger.warning("ffprobe_duration_failed", path=str(path), exc_info=True)
    return 0.0
