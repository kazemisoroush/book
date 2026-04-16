"""Tests for VibeVoiceMusicProvider."""
import wave
from pathlib import Path

from src.audio.music.vibevoice_music_provider import VibeVoiceMusicProvider


class TestVibeVoiceMusicProviderGenerate:
    """Tests for VibeVoiceMusicProvider.generate."""

    def test_generate_returns_output_path(self, tmp_path: Path) -> None:
        # Arrange
        provider = VibeVoiceMusicProvider()
        output_path = tmp_path / "music.wav"

        # Act
        result = provider.generate("epic orchestral theme", output_path, duration_seconds=1.0)

        # Assert
        assert result == output_path

    def test_generate_writes_valid_wav_file(self, tmp_path: Path) -> None:
        # Arrange
        provider = VibeVoiceMusicProvider()
        output_path = tmp_path / "music.wav"

        # Act
        provider.generate("soft piano", output_path, duration_seconds=0.5)

        # Assert
        with wave.open(str(output_path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000

    def test_generate_returns_none_on_invalid_path(self) -> None:
        # Arrange
        provider = VibeVoiceMusicProvider()
        bad_path = Path("/nonexistent_root_dir/no_perms/music.wav")

        # Act
        result = provider.generate("jazz", bad_path)

        # Assert
        assert result is None
