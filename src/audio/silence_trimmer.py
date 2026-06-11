"""SilenceTrimmer: strip vendor-baked silence from synthesised beat MP3s."""
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class SilenceTrimmer:
    """Trim leading and trailing silence from an MP3 via ffmpeg silenceremove.

    The vendor-baked silence is replaced by a tiny fade-in and fade-out so the
    transition into the downstream-inserted silence does not click.
    """

    def __init__(
        self,
        threshold_db: float = -50.0,
        fade_in_seconds: float = 0.005,
        fade_out_seconds: float = 0.015,
        sample_rate: int = 44100,
        bitrate: str = "128k",
    ) -> None:
        self._threshold_db = threshold_db
        self._fade_in_seconds = fade_in_seconds
        self._fade_out_seconds = fade_out_seconds
        self._sample_rate = sample_rate
        self._bitrate = bitrate

    def trim(self, input_path: Path, output_path: Path) -> Path:
        """Trim silence from *input_path*; write result to *output_path*."""
        threshold = f"{self._threshold_db}dB"
        silenceremove = (
            "silenceremove="
            "start_periods=1:start_silence=0:"
            f"start_threshold={threshold}:"
            "stop_periods=-1:stop_silence=0:"
            f"stop_threshold={threshold}"
        )
        afilter = (
            f"{silenceremove},"
            f"afade=t=in:st=0:d={self._fade_in_seconds},"
            f"areverse,afade=t=in:st=0:d={self._fade_out_seconds},areverse"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", afilter,
            "-ar", str(self._sample_rate),
            "-ac", "1",
            "-acodec", "libmp3lame",
            "-b:a", self._bitrate,
            str(output_path),
        ]
        logger.debug(
            "silence_trim",
            input=str(input_path),
            output=str(output_path),
            threshold_db=self._threshold_db,
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg silence trim failed (exit {result.returncode}):\n"
                f"stderr: {result.stderr}"
            )
        return output_path
