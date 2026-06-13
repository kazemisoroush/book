"""Tests for PeakLevelTrimmer."""
import re
import subprocess
from pathlib import Path

import pytest

from src.audio.tts.audio_trimmer.peak_level_trimmer import PeakLevelTrimmer

_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")


def _probe_peak_db(path: Path) -> float:
    """Return the max_volume in dBFS via ffmpeg volumedetect."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(path),
            "-af", "volumedetect",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, check=True,
    )
    for line in result.stderr.splitlines():
        match = _MAX_VOLUME_RE.search(line)
        if match:
            return float(match.group(1))
    raise RuntimeError(f"max_volume not found:\n{result.stderr}")


def _make_sine_mp3(path: Path, gain_db: float, duration: float = 1.0) -> Path:
    """Build a 440 Hz sine at the requested *gain_db* below full scale."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"sine=frequency=440:duration={duration}:sample_rate=44100",
        "-af", f"volume={gain_db}dB",
        "-ar", "44100", "-ac", "1",
        "-acodec", "libmp3lame", "-b:a", "128k",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg test helper failed: {result.stderr}")
    return path


class TestPeakLevelTrimmer:
    def test_pushes_quiet_input_up_to_target_peak(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_sine_mp3(tmp_path / "input.mp3", gain_db=-25.0)
        output_path = tmp_path / "out.mp3"

        # Act
        PeakLevelTrimmer(peak_target_db=-1.0).trim(input_path, output_path)

        # Assert
        assert abs(_probe_peak_db(output_path) - (-1.0)) < 1.0

    def test_pulls_loud_input_down_to_target_peak(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_sine_mp3(tmp_path / "input.mp3", gain_db=-2.0)
        output_path = tmp_path / "out.mp3"

        # Act
        PeakLevelTrimmer(peak_target_db=-6.0).trim(input_path, output_path)

        # Assert
        assert abs(_probe_peak_db(output_path) - (-6.0)) < 1.0

    def test_two_beats_at_different_levels_land_at_same_peak(self, tmp_path: Path) -> None:
        # Arrange
        loud = _make_sine_mp3(tmp_path / "loud.mp3", gain_db=-3.0)
        quiet = _make_sine_mp3(tmp_path / "quiet.mp3", gain_db=-20.0)
        loud_out = tmp_path / "loud_out.mp3"
        quiet_out = tmp_path / "quiet_out.mp3"
        trimmer = PeakLevelTrimmer(peak_target_db=-1.0)

        # Act
        trimmer.trim(loud, loud_out)
        trimmer.trim(quiet, quiet_out)

        # Assert
        assert abs(_probe_peak_db(loud_out) - _probe_peak_db(quiet_out)) < 1.0

    def test_skips_when_output_already_exists(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_sine_mp3(tmp_path / "input.mp3", gain_db=-10.0)
        output_path = tmp_path / "out.mp3"
        output_path.write_bytes(b"already-there")

        # Act
        PeakLevelTrimmer().trim(input_path, output_path)

        # Assert
        assert output_path.read_bytes() == b"already-there"

    def test_copies_input_through_when_peak_cannot_be_measured(self, tmp_path: Path) -> None:
        # Arrange
        input_path = tmp_path / "input.mp3"
        input_path.write_bytes(b"not actually mp3")
        output_path = tmp_path / "out.mp3"

        # Act
        PeakLevelTrimmer().trim(input_path, output_path)

        # Assert
        assert output_path.read_bytes() == b"not actually mp3"

    def test_raises_on_ffmpeg_encode_failure(self, tmp_path: Path) -> None:
        # Arrange: a real mp3 lets _measure_peak_db succeed; an invalid bitrate
        # forces the encode itself to fail with a clear ffmpeg error.
        input_path = _make_sine_mp3(tmp_path / "input.mp3", gain_db=-10.0)
        bad_trimmer = PeakLevelTrimmer(bitrate="not-a-bitrate")

        # Act / Assert
        with pytest.raises(RuntimeError, match="peak level trim failed"):
            bad_trimmer.trim(input_path, tmp_path / "out.mp3")
