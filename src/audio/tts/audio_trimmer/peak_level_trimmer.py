"""Bring each beat MP3 to a common peak ceiling so seams between beats sound level-matched."""
import re
import shutil
import subprocess
from pathlib import Path

import structlog

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer

logger = structlog.get_logger(__name__)

_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")


class PeakLevelTrimmer(AudioTrimmer):
    """Apply a high-pass filter and scale each beat to a fixed peak ceiling."""

    def __init__(
        self,
        peak_target_db: float = -3.0,
        highpass_hz: float = 80.0,
        sample_rate: int = 44100,
        bitrate: str = "128k",
    ) -> None:
        self._peak_target_db = peak_target_db
        self._highpass_hz = highpass_hz
        self._sample_rate = sample_rate
        self._bitrate = bitrate

    def _trim(self, input_path: Path, output_path: Path) -> Path:
        """Highpass and gain-shift *input_path* into *output_path* at the configured peak."""
        peak_db = self._measure_peak_db(input_path)
        if peak_db is None:
            logger.warning(
                "peak_level_trim_no_peak_measured_copying_through",
                input=str(input_path),
                output=str(output_path),
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input_path, output_path)
            return output_path

        gain_db = self._peak_target_db - peak_db
        afilter = (
            f"highpass=f={self._highpass_hz},"
            f"volume=volume={gain_db}dB:precision=double"
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
            "peak_level_trim",
            input=str(input_path),
            output=str(output_path),
            peak_db=peak_db,
            gain_db=gain_db,
            peak_target_db=self._peak_target_db,
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg peak level trim failed (exit {result.returncode}):\n"
                f"stderr: {result.stderr}"
            )
        return output_path

    def _measure_peak_db(self, input_path: Path) -> float | None:
        """Return the input's max_volume in dBFS, or None when ffmpeg cannot measure it."""
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(input_path),
                "-af", "volumedetect",
                "-f", "null", "-",
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return None
        for line in result.stderr.splitlines():
            match = _MAX_VOLUME_RE.search(line)
            if match:
                return float(match.group(1))
        return None
