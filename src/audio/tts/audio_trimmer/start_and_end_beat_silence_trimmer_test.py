"""Tests for StartAndEndBeatSilenceTrimmer."""
import subprocess
from pathlib import Path

import pytest

from src.audio.tts.audio_trimmer.start_and_end_beat_silence_trimmer import (
    StartAndEndBeatSilenceTrimmer,
)


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


class TestStartAndEndBeatSilenceTrimmer:
    def test_trims_leading_and_trailing_silence(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.4, audible=0.5, trailing_silence=0.4,
        )
        output_path = tmp_path / "trimmed.mp3"

        # Act
        StartAndEndBeatSilenceTrimmer().trim(input_path, output_path)

        # Assert
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        assert 0.4 <= _probe_duration_seconds(output_path) <= 0.7

    def test_preserves_internal_silence(self, tmp_path: Path) -> None:
        # Arrange
        input_path = tmp_path / "input.mp3"
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5:sample_rate=44100",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.6",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5:sample_rate=44100",
                "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1",
                "-ar", "44100", "-ac", "1",
                "-acodec", "libmp3lame", "-b:a", "128k",
                str(input_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        output_path = tmp_path / "trimmed.mp3"

        # Act
        StartAndEndBeatSilenceTrimmer().trim(input_path, output_path)

        # Assert
        assert _probe_duration_seconds(output_path) >= 1.4

    def test_preserves_audible_content(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.2, audible=1.5, trailing_silence=0.2,
        )
        output_path = tmp_path / "trimmed.mp3"

        # Act
        StartAndEndBeatSilenceTrimmer().trim(input_path, output_path)

        # Assert
        assert 1.3 <= _probe_duration_seconds(output_path) <= 1.7

    def test_no_op_on_already_clean_input(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.0, audible=0.5, trailing_silence=0.0,
        )
        original = _probe_duration_seconds(input_path)
        output_path = tmp_path / "trimmed.mp3"

        # Act
        StartAndEndBeatSilenceTrimmer().trim(input_path, output_path)

        # Assert
        assert abs(_probe_duration_seconds(output_path) - original) < 0.1

    def test_idempotent(self, tmp_path: Path) -> None:
        # Arrange
        input_path = _make_mp3(
            tmp_path / "input.mp3",
            leading_silence=0.3, audible=0.6, trailing_silence=0.3,
        )
        once = tmp_path / "once.mp3"
        twice = tmp_path / "twice.mp3"
        trimmer = StartAndEndBeatSilenceTrimmer()

        # Act
        trimmer.trim(input_path, once)
        trimmer.trim(once, twice)

        # Assert
        assert abs(_probe_duration_seconds(once) - _probe_duration_seconds(twice)) < 0.05

    def test_raises_on_ffmpeg_failure(self, tmp_path: Path) -> None:
        # Arrange
        bogus = tmp_path / "does_not_exist.mp3"

        # Act / Assert
        with pytest.raises(RuntimeError, match="silence trim failed"):
            StartAndEndBeatSilenceTrimmer().trim(bogus, tmp_path / "out.mp3")

    def test_falls_back_to_input_when_silenceremove_strips_everything(
        self, tmp_path: Path,
    ) -> None:
        # Arrange: a beat that's entirely below the -50 dB threshold means
        # silenceremove leaves an empty MP3, which would corrupt downstream
        # decoders. The trimmer must copy the input through instead.
        input_path = tmp_path / "input.mp3"
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i",
                "sine=frequency=440:duration=0.5:sample_rate=44100",
                "-af", "volume=-90dB",
                "-ar", "44100", "-ac", "1",
                "-acodec", "libmp3lame", "-b:a", "128k",
                str(input_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        output_path = tmp_path / "out.mp3"

        # Act
        StartAndEndBeatSilenceTrimmer().trim(input_path, output_path)

        # Assert
        assert output_path.exists()
        assert output_path.read_bytes() == input_path.read_bytes()
