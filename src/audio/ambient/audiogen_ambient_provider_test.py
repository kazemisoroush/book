"""Tests for AudioGenAmbientProvider."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio.ambient.audiogen_ambient_provider import AudioGenAmbientProvider
from src.domain.models import Scene


class TestAudioGenAmbientProviderInit:
    def test_default_model_and_device(self, tmp_path: Path) -> None:
        provider = AudioGenAmbientProvider(books_dir=tmp_path)

        assert provider._books_dir == tmp_path
        assert provider._model_id == "facebook/audiogen-medium"
        assert provider._device == "cpu"
        assert provider._model is None


class TestAudioGenAmbientProviderGenerate:
    """Internal _generate helper still used by AudioOrchestrator."""

    def test_generate_calls_model_and_saves_file(self, tmp_path: Path) -> None:
        provider = AudioGenAmbientProvider(books_dir=tmp_path)
        output_path = tmp_path / "ambient.wav"

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav

        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model

        mock_ta = MagicMock()
        with patch(
            "src.audio.ambient.audiogen_ambient_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            result = provider._generate(
                "forest ambience", output_path, duration_seconds=30.0
            )

        mock_model.set_generation_params.assert_called_once_with(duration=30.0)
        mock_model.generate.assert_called_once_with(["forest ambience"])
        mock_ta.save.assert_called_once_with(str(output_path), mock_wav, 16000)
        assert result == output_path

    def test_generate_returns_none_on_model_error(self, tmp_path: Path) -> None:
        provider = AudioGenAmbientProvider(books_dir=tmp_path)
        output_path = tmp_path / "ambient.wav"

        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("OOM")
        provider._model = mock_model

        with patch(
            "src.audio.ambient.audiogen_ambient_provider._import_torchaudio",
            return_value=MagicMock(),
        ):
            result = provider._generate(
                "ocean waves", output_path, duration_seconds=60.0
            )

        assert result is None

    def test_ensure_loaded_raises_helpful_error_when_audiocraft_missing(
        self, tmp_path: Path
    ) -> None:
        provider = AudioGenAmbientProvider(books_dir=tmp_path)

        with patch.dict("sys.modules", {"audiocraft": None, "audiocraft.models": None}):
            with pytest.raises(ImportError, match="audiocraft"):
                provider._ensure_loaded()


class TestAudioGenAmbientProviderProvide:
    def test_writes_to_per_book_path(self, tmp_path: Path, monkeypatch) -> None:
        provider = AudioGenAmbientProvider(books_dir=tmp_path)
        scene = Scene(
            scene_id="meryton_ball",
            environment="ballroom",
            ambient_prompt="distant orchestra and chatter",
        )

        mock_wav = MagicMock()
        mock_wav.cpu.return_value = mock_wav
        mock_model = MagicMock()
        mock_model.generate.return_value = [mock_wav]
        mock_model.sample_rate = 16000
        provider._model = mock_model

        expected = (
            tmp_path / "pride_and_prejudice" / "audio" / "ambient" / "audiogen"
            / "meryton_ball.wav"
        )

        def fake_save(target: str, _wav, _rate) -> None:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(b"fake-wav")

        mock_ta = MagicMock()
        mock_ta.save.side_effect = fake_save

        monkeypatch.setattr(
            "src.audio.ambient.audiogen_ambient_provider._wav_duration_seconds",
            lambda _path: 12.5,
        )
        with patch(
            "src.audio.ambient.audiogen_ambient_provider._import_torchaudio",
            return_value=mock_ta,
        ):
            duration = provider.provide(scene, "pride_and_prejudice")

        assert expected.exists()
        assert duration == 12.5

    def test_raises_when_scene_has_no_ambient_prompt(self, tmp_path: Path) -> None:
        provider = AudioGenAmbientProvider(books_dir=tmp_path)
        scene = Scene(scene_id="silent_room", environment="empty")

        with pytest.raises(ValueError, match="ambient_prompt"):
            provider.provide(scene, "any_book")
