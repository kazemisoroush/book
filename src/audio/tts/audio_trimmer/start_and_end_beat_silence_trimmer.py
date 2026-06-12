"""Strip vendor-baked silence from the start and end of a beat MP3."""
import subprocess
from pathlib import Path

import structlog

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer

logger = structlog.get_logger(__name__)


class StartAndEndBeatSilenceTrimmer(AudioTrimmer):
    """Trim only the leading and trailing silence of a beat MP3."""

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

    def _trim(self, input_path: Path, output_path: Path) -> Path:
        """Trim edge silence from *input_path* and write the result to *output_path*."""
        threshold = f"{self._threshold_db}dB"
        trim_leading = (
            "silenceremove="
            "start_periods=1:start_silence=0:"
            f"start_threshold={threshold}"
        )
        afilter = (
            f"{trim_leading},"
            f"afade=t=in:st=0:d={self._fade_in_seconds},"
            "areverse,"
            f"{trim_leading},"
            f"afade=t=in:st=0:d={self._fade_out_seconds},"
            "areverse"
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
