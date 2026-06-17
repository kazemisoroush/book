"""Tests for AudioGenSoundEffectProvider."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.sound_effect.audiogen_sound_effect_provider import (
    AudioGenSoundEffectProvider,
)
from src.domain.beat import Beat, BeatType
from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage
from src.storage.objects import SFXBeatRef


def _audio_store(tmp_path: Path) -> AudioStore:
    return AudioStore(LocalStorage(tmp_path))


class TestAudioGenSoundEffectProviderInit:
    def test_default_model_and_device(self, tmp_path: Path) -> None:
        # Arrange / Act
        provider = AudioGenSoundEffectProvider(audio_store=_audio_store(tmp_path))

        # Assert
        assert provider._model_id == "facebook/audiogen-medium"
        assert provider._device == "cpu"
        assert provider._model is None


class TestAudioGenSoundEffectProviderGenerate:
    """Internal _generate helper used by SfxWorkflow."""

    def test_generate_calls_model_and_saves_file(self, tmp_path: Path) -> None:
        # Arrange
        provider = AudioGenSoundEffectProvider(audio_store=_audio_store(tmp_path))
        ref = SFXBeatRef("book", "audiogen", 5, extension="wav")

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav
        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model

        mock_ta = MagicMock()

        # Act
        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            ok = provider._generate("door slam", ref, duration_seconds=2.0)

        # Assert
        mock_model.set_generation_params.assert_called_once_with(duration=2.0)
        mock_model.generate.assert_called_once_with(["door slam"])
        expected_path = str(
            tmp_path / "book" / "audio" / "sfx" / "audiogen" / "beat_0005.wav",
        )
        mock_ta.save.assert_called_once_with(expected_path, mock_wav, 16000)
        assert ok is True

    def test_generate_returns_false_on_model_error(self, tmp_path: Path) -> None:
        # Arrange
        provider = AudioGenSoundEffectProvider(audio_store=_audio_store(tmp_path))
        ref = SFXBeatRef("book", "audiogen", 1, extension="wav")

        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("GPU OOM")
        provider._model = mock_model

        # Act
        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=MagicMock(),
        ):
            ok = provider._generate("thunder", ref, duration_seconds=2.0)

        # Assert
        assert ok is False

    def test_ensure_loaded_raises_helpful_error_when_audiocraft_missing(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        provider = AudioGenSoundEffectProvider(audio_store=_audio_store(tmp_path))

        # Act / Assert
        with patch.dict("sys.modules", {"audiocraft": None, "audiocraft.models": None}):
            with pytest.raises(ImportError, match="audiocraft"):
                provider._ensure_loaded()


class TestAudioGenSoundEffectProviderProvide:
    def test_writes_to_per_book_path_with_beat_counter(self, tmp_path: Path) -> None:
        # Arrange
        provider = AudioGenSoundEffectProvider(audio_store=_audio_store(tmp_path))
        beat = Beat(text="door slam", beat_type=BeatType.SOUND_EFFECT)

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav
        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model

        def fake_save(target: str, _wav: object, _rate: object) -> None:
            Path(target).write_bytes(b"fake-wav")

        mock_ta = MagicMock()
        mock_ta.save.side_effect = fake_save

        # Act
        with patch(
            "src.audio.sound_effect.audiogen_sound_effect_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            provider.provide(beat, "pride_and_prejudice")

        # Assert
        expected = (
            tmp_path / "pride_and_prejudice" / "audio" / "sfx" / "audiogen"
            / "beat_0001.wav"
        )
        assert expected.exists()
