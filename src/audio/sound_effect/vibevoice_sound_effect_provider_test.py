"""Tests for VibeVoiceSoundEffectProvider."""
import wave
from pathlib import Path

from src.audio.sound_effect.vibevoice_sound_effect_provider import VibeVoiceSoundEffectProvider


class TestVibeVoiceSoundEffectProviderGenerate:
    """Tests for VibeVoiceSoundEffectProvider.generate."""

    def test_generate_returns_output_path(self, tmp_path: Path) -> None:
        # Arrange
        provider = VibeVoiceSoundEffectProvider()
        output_path = tmp_path / "sfx.wav"

        # Act
        result = provider.generate("door slam", output_path, duration_seconds=1.0)

        # Assert
        assert result == output_path

    def test_generate_writes_valid_wav_file(self, tmp_path: Path) -> None:
        # Arrange
        provider = VibeVoiceSoundEffectProvider()
        output_path = tmp_path / "sfx.wav"

        # Act
        provider.generate("thunder clap", output_path, duration_seconds=0.5)

        # Assert
        with wave.open(str(output_path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000

    def test_generate_returns_none_on_invalid_path(self) -> None:
        # Arrange
        provider = VibeVoiceSoundEffectProvider()
        bad_path = Path("/nonexistent_root_dir/no_perms/sfx.wav")

        # Act
        result = provider.generate("explosion", bad_path)

        # Assert
        assert result is None
