"""Tests for VibeVoiceAmbientProvider."""
import wave
from pathlib import Path

from src.audio.ambient.vibevoice_ambient_provider import VibeVoiceAmbientProvider


class TestVibeVoiceAmbientProviderGenerate:
    """Tests for VibeVoiceAmbientProvider.generate."""

    def test_generate_returns_output_path(self, tmp_path: Path) -> None:
        # Arrange
        provider = VibeVoiceAmbientProvider()
        output_path = tmp_path / "ambient.wav"

        # Act
        result = provider.generate("forest ambience", output_path, duration_seconds=1.0)

        # Assert
        assert result == output_path

    def test_generate_writes_valid_wav_file(self, tmp_path: Path) -> None:
        # Arrange
        provider = VibeVoiceAmbientProvider()
        output_path = tmp_path / "ambient.wav"

        # Act
        provider.generate("ocean waves", output_path, duration_seconds=0.5)

        # Assert
        with wave.open(str(output_path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000

    def test_generate_returns_none_on_invalid_path(self) -> None:
        # Arrange
        provider = VibeVoiceAmbientProvider()
        bad_path = Path("/nonexistent_root_dir/no_perms/ambient.wav")

        # Act
        result = provider.generate("rain", bad_path)

        # Assert
        assert result is None
