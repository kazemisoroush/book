"""Tests for AudioGenSoundEffectProvider."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.sound_effect.audiogen_sound_effect_provider import (
    AudioGenSoundEffectProvider,
)


class TestAudioGenSoundEffectProviderInit:
    """Tests for AudioGenSoundEffectProvider constructor."""

    def test_default_model_and_device(self) -> None:
        # Arrange / Act
        provider = AudioGenSoundEffectProvider()

        # Assert
        assert provider._model_id == "facebook/audiogen-medium"
        assert provider._device == "cpu"
        assert provider._model is None  # Not loaded yet


class TestAudioGenSoundEffectProviderGenerate:
    """Tests for AudioGenSoundEffectProvider.generate."""

    def test_generate_calls_model_and_saves_file(self, tmp_path: Path) -> None:
        # Arrange
        provider = AudioGenSoundEffectProvider()
        output_path = tmp_path / "sfx.wav"

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav

        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model  # inject pre-loaded mock

        mock_ta = MagicMock()
        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            # Act
            result = provider._generate("door slam", output_path, duration_seconds=2.0)

        # Assert
        mock_model.set_generation_params.assert_called_once_with(duration=2.0)
        mock_model.generate.assert_called_once_with(["door slam"])
        mock_ta.save.assert_called_once_with(str(output_path), mock_wav, 16000)
        assert result == output_path

    def test_generate_returns_none_on_model_error(self, tmp_path: Path) -> None:
        # Arrange
        provider = AudioGenSoundEffectProvider()
        output_path = tmp_path / "sfx.wav"

        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("GPU OOM")
        provider._model = mock_model

        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=MagicMock(),
        ):
            # Act
            result = provider._generate("thunder", output_path, duration_seconds=2.0)

        # Assert
        assert result is None

    def test_ensure_loaded_raises_helpful_error_when_audiocraft_missing(self) -> None:
        # Arrange — model not loaded; audiocraft not available
        provider = AudioGenSoundEffectProvider()

        with patch.dict("sys.modules", {"audiocraft": None, "audiocraft.models": None}):
            # Act / Assert
            with pytest.raises(ImportError, match="audiocraft"):
                provider._ensure_loaded()
