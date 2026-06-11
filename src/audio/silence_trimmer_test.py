"""Tests for SilenceTrimmer."""
import subprocess
from pathlib import Path

import pytest

from src.audio.silence_trimmer import SilenceTrimmer


def _probe_duration_seconds(path: Path) -> float:
    """Return audio duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _make_mp3(
    path: Path,
    leading_silence: float,
    audible: float,
    trailing_silence: float,
) -> Path:
    """Build an MP3 of [silence|440Hz sine|silence] for trim assertions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={leading_silence}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={audible}:sample_rate=44100",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={trailing_silence}",
        "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1",
        "-ar", "44100", "-ac", "1",
        "-acodec", "libmp3lame", "-b:a", "128k",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg test helper failed: {result.stderr}")
    return path


class TestSilenceTrimmer:
    def test_trims_leading_and_trailing_silence(self, tmp_path: Path) -> None:
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.4, audible=0.5, trailing_silence=0.4,
        )
        assert _probe_duration_seconds(input_path) >= 1.2

        output_path = tmp_path / "trimmed.mp3"
        SilenceTrimmer().trim(input_path, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0
        trimmed = _probe_duration_seconds(output_path)
        assert 0.4 <= trimmed <= 0.7, f"expected ~0.5s, got {trimmed:.3f}s"

    def test_preserves_audible_content(self, tmp_path: Path) -> None:
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.2, audible=1.5, trailing_silence=0.2,
        )

        output_path = tmp_path / "trimmed.mp3"
        SilenceTrimmer().trim(input_path, output_path)

        trimmed = _probe_duration_seconds(output_path)
        assert 1.3 <= trimmed <= 1.7, f"expected ~1.5s, got {trimmed:.3f}s"

    def test_no_op_on_already_clean_input(self, tmp_path: Path) -> None:
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.0, audible=0.5, trailing_silence=0.0,
        )
        original = _probe_duration_seconds(input_path)

        output_path = tmp_path / "trimmed.mp3"
        SilenceTrimmer().trim(input_path, output_path)
        trimmed = _probe_duration_seconds(output_path)

        assert abs(trimmed - original) < 0.1

    def test_idempotent(self, tmp_path: Path) -> None:
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.3, audible=0.6, trailing_silence=0.3,
        )

        once = tmp_path / "once.mp3"
        twice = tmp_path / "twice.mp3"
        trimmer = SilenceTrimmer()
        trimmer.trim(input_path, once)
        trimmer.trim(once, twice)

        assert abs(_probe_duration_seconds(once) - _probe_duration_seconds(twice)) < 0.05

    def test_raises_on_ffmpeg_failure(self, tmp_path: Path) -> None:
        bogus = tmp_path / "does_not_exist.mp3"
        with pytest.raises(RuntimeError, match="silence trim failed"):
            SilenceTrimmer().trim(bogus, tmp_path / "out.mp3")
