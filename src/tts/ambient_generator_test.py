"""Tests for ambient audio generation (US-011).

Tests verify:
  - get_ambient_audio returns None when scene has no ambient_prompt
  - get_ambient_audio calls ElevenLabs sound effects API with correct params
  - get_ambient_audio caches by scene_id (no duplicate API calls)
  - get_ambient_audio returns None and logs warning on API failure
  - duration_seconds parameter is forwarded to API
"""
from pathlib import Path
from unittest.mock import MagicMock

from src.domain.models import Scene
from src.tts.ambient_generator import get_ambient_audio


class TestGetAmbientAudioNoPrompt:
    """get_ambient_audio returns None when ambient_prompt is None."""

    def test_returns_none_when_no_ambient_prompt(self, tmp_path: Path) -> None:
        """Scene without ambient_prompt produces no ambient audio."""
        # Arrange
        scene = Scene(scene_id="bare", environment="indoor_quiet")
        client = MagicMock()

        # Act
        result = get_ambient_audio(scene, tmp_path, client)

        # Assert
        assert result is None
        client.text_to_sound_effects.convert.assert_not_called()


class TestGetAmbientAudioCallsAPI:
    """get_ambient_audio calls the ElevenLabs sound effects API."""

    def test_calls_api_with_prompt_and_duration(self, tmp_path: Path) -> None:
        """API is called with scene.ambient_prompt and duration_seconds."""
        # Arrange
        scene = Scene(
            scene_id="drawing_room",
            environment="indoor_quiet",
            ambient_prompt="clock ticking, distant footsteps",
            ambient_volume=-18.0,
        )
        client = MagicMock()
        client.text_to_sound_effects.convert.return_value = iter([b"\xff" * 100])

        # Act
        result = get_ambient_audio(scene, tmp_path, client, duration_seconds=45.0)

        # Assert
        client.text_to_sound_effects.convert.assert_called_once()
        call_kwargs = client.text_to_sound_effects.convert.call_args
        assert call_kwargs.kwargs["text"] == "clock ticking, distant footsteps"
        assert call_kwargs.kwargs["duration_seconds"] == 45.0
        assert result is not None
        assert result.exists()


class TestGetAmbientAudioCaching:
    """get_ambient_audio caches results by scene_id."""

    def test_second_call_uses_cache(self, tmp_path: Path) -> None:
        """Calling twice with the same scene_id does not call the API again."""
        # Arrange
        scene = Scene(
            scene_id="drawing_room",
            environment="indoor_quiet",
            ambient_prompt="clock ticking",
            ambient_volume=-18.0,
        )
        client = MagicMock()
        client.text_to_sound_effects.convert.return_value = iter([b"\xff" * 100])

        # Act
        first = get_ambient_audio(scene, tmp_path, client)
        # Reset the mock's return value for a fresh iterator
        client.text_to_sound_effects.convert.return_value = iter([b"\xff" * 100])
        second = get_ambient_audio(scene, tmp_path, client)

        # Assert
        assert first == second
        assert client.text_to_sound_effects.convert.call_count == 1


class TestGetAmbientAudioAPIFailure:
    """get_ambient_audio returns None on API failure."""

    def test_returns_none_on_api_error(self, tmp_path: Path) -> None:
        """API exception is caught, warning logged, None returned."""
        # Arrange
        scene = Scene(
            scene_id="battlefield",
            environment="battlefield",
            ambient_prompt="clashing swords, war cries",
            ambient_volume=-16.0,
        )
        client = MagicMock()
        client.text_to_sound_effects.convert.side_effect = Exception("API down")

        # Act
        result = get_ambient_audio(scene, tmp_path, client)

        # Assert
        assert result is None


class TestGetAmbientAudioDefaultDuration:
    """get_ambient_audio uses 60.0 as default duration_seconds."""

    def test_default_duration_is_60(self, tmp_path: Path) -> None:
        """When duration_seconds is not specified, 60.0 is used."""
        # Arrange
        scene = Scene(
            scene_id="forest",
            environment="forest",
            ambient_prompt="birds chirping, wind through leaves",
            ambient_volume=-18.0,
        )
        client = MagicMock()
        client.text_to_sound_effects.convert.return_value = iter([b"\xff" * 100])

        # Act
        get_ambient_audio(scene, tmp_path, client)

        # Assert
        call_kwargs = client.text_to_sound_effects.convert.call_args
        assert call_kwargs.kwargs["duration_seconds"] == 60.0
