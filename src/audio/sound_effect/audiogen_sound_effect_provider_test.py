"""Tests for AudioGenSoundEffectProvider."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.sound_effect.audiogen_sound_effect_provider import (
    AudioGenSoundEffectProvider,
)
from src.domain.beat import Beat, BeatType


class TestAudioGenSoundEffectProviderInit:
    def test_default_model_and_device(self, tmp_path: Path) -> None:
        provider = AudioGenSoundEffectProvider(books_dir=tmp_path)

        assert provider._books_dir == tmp_path
        assert provider._model_id == "facebook/audiogen-medium"
        assert provider._device == "cpu"
        assert provider._model is None


class TestAudioGenSoundEffectProviderGenerate:
    """Internal _generate helper still used by AudioOrchestrator."""

    def test_generate_calls_model_and_saves_file(self, tmp_path: Path) -> None:
        provider = AudioGenSoundEffectProvider(books_dir=tmp_path)
        output_path = tmp_path / "sfx.wav"

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav
        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model

        mock_ta = MagicMock()
        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            result = provider._generate("door slam", output_path, duration_seconds=2.0)

        mock_model.set_generation_params.assert_called_once_with(duration=2.0)
        mock_model.generate.assert_called_once_with(["door slam"])
        mock_ta.save.assert_called_once_with(str(output_path), mock_wav, 16000)
        assert result == output_path

    def test_generate_returns_none_on_model_error(self, tmp_path: Path) -> None:
        provider = AudioGenSoundEffectProvider(books_dir=tmp_path)
        output_path = tmp_path / "sfx.wav"

        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("GPU OOM")
        provider._model = mock_model

        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=MagicMock(),
        ):
            result = provider._generate("thunder", output_path, duration_seconds=2.0)

        assert result is None

    def test_ensure_loaded_raises_helpful_error_when_audiocraft_missing(
        self, tmp_path: Path
    ) -> None:
        provider = AudioGenSoundEffectProvider(books_dir=tmp_path)

        with patch.dict("sys.modules", {"audiocraft": None, "audiocraft.models": None}):
            with pytest.raises(ImportError, match="audiocraft"):
                provider._ensure_loaded()


class TestAudioGenSoundEffectProviderProvide:
    def test_writes_to_per_book_path_with_beat_counter(self, tmp_path: Path) -> None:
        provider = AudioGenSoundEffectProvider(books_dir=tmp_path)
        beat = Beat(text="door slam", beat_type=BeatType.SOUND_EFFECT)

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav
        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model

        def fake_save(target: str, _wav, _rate) -> None:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(b"fake-wav")

        mock_ta = MagicMock()
        mock_ta.save.side_effect = fake_save

        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            provider.provide(beat, "pride_and_prejudice")

        expected = (
            tmp_path / "pride_and_prejudice" / "audio" / "sfx" / "audiogen"
            / "beat_0001.wav"
        )
        assert expected.exists()
