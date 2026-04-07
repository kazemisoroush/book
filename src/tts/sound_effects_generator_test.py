"""Tests for sound effects generator (US-023 Cinematic Sound Effects)."""
import hashlib
from pathlib import Path
from unittest.mock import Mock

from src.tts.sound_effects_generator import get_sound_effect


class TestGetSoundEffect:
    """Tests for get_sound_effect() function."""

    def test_returns_none_when_client_is_none(self, tmp_path: Path) -> None:
        """get_sound_effect() returns None gracefully when client is None."""
        # Arrange
        description = "dry cough"
        output_dir = tmp_path

        # Act
        result = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=None,
            duration_seconds=2.0,
        )

        # Assert
        assert result is None

    def test_caches_by_description_hash(self, tmp_path: Path) -> None:
        """get_sound_effect() caches result by description hash."""
        # Arrange
        description = "dry cough"
        output_dir = tmp_path
        cache_dir = output_dir / "sfx"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Compute expected cache filename
        description_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
        expected_path = cache_dir / f"{description_hash}.mp3"

        # Create a mock MP3 file (fake audio)
        expected_path.write_bytes(b"fake_mp3_data")

        # Create a mock client that should NOT be called (cache hit)
        mock_client = Mock()
        mock_client.text_to_sound_effects = Mock()

        # Act
        result = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Assert
        assert result == expected_path
        assert result.exists()
        # Client should not be called since cache exists
        mock_client.text_to_sound_effects.assert_not_called()

    def test_generates_and_caches_on_first_call(self, tmp_path: Path) -> None:
        """get_sound_effect() generates via API on first call and caches result."""
        # Arrange
        description = "thunder crash"
        output_dir = tmp_path
        cache_dir = output_dir / "sfx"

        # Create a mock client -- .convert() returns an iterator of bytes chunks
        mock_client = Mock()
        mock_client.text_to_sound_effects.convert.return_value = iter(
            [b"generated_", b"mp3_data"]
        )

        # Compute expected cache filename
        description_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
        expected_path = cache_dir / f"{description_hash}.mp3"

        # Act
        result = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Assert
        assert result == expected_path
        assert result.exists()
        assert result.read_bytes() == b"generated_mp3_data"
        # Client.text_to_sound_effects.convert should have been called (not the namespace directly)
        mock_client.text_to_sound_effects.convert.assert_called_once()

    def test_same_description_reuses_cache(self, tmp_path: Path) -> None:
        """get_sound_effect() with same description reuses cached file."""
        # Arrange
        description = "firm knock on wooden door"
        output_dir = tmp_path
        mock_client = Mock()

        # First call — generates via .convert() returning iterator
        mock_client.text_to_sound_effects.convert.return_value = iter(
            [b"knock_audio_data"]
        )

        # Act — first call
        result1 = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Act — second call with same description
        mock_client.reset_mock()
        result2 = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Assert
        assert result1 == result2
        assert result1 is not None
        assert result1.exists()
        # Second call should NOT call the client (cache hit)
        mock_client.text_to_sound_effects.convert.assert_not_called()

    def test_different_descriptions_generate_different_files(self, tmp_path: Path) -> None:
        """get_sound_effect() with different descriptions generates different cache files."""
        # Arrange
        output_dir = tmp_path
        mock_client = Mock()

        # Configure mock to return different iterators for different calls
        mock_client.text_to_sound_effects.convert.side_effect = [
            iter([b"cough_audio_1"]),
            iter([b"rain_audio_2"]),
        ]

        # Act
        result1 = get_sound_effect(
            description="dry cough",
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )
        result2 = get_sound_effect(
            description="heavy rain",
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Assert
        assert result1 != result2
        assert result1 is not None
        assert result2 is not None
        assert result1.exists()
        assert result2.exists()
        assert result1.read_bytes() == b"cough_audio_1"
        assert result2.read_bytes() == b"rain_audio_2"

    def test_handles_api_failure_gracefully(self, tmp_path: Path) -> None:
        """get_sound_effect() returns None on API failure (logs warning, doesn't raise)."""
        # Arrange
        description = "sound effect"
        output_dir = tmp_path
        mock_client = Mock()
        mock_client.text_to_sound_effects.convert.side_effect = RuntimeError(
            "API connection failed"
        )

        # Act — should not raise, returns None
        result = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Assert
        assert result is None

    def test_passes_correct_parameters_to_api(self, tmp_path: Path) -> None:
        """get_sound_effect() calls .convert() with correct text and duration."""
        # Arrange
        description = "birds chirping"
        duration_seconds = 3.5
        output_dir = tmp_path
        mock_client = Mock()
        mock_client.text_to_sound_effects.convert.return_value = iter(
            [b"birds_audio"]
        )

        # Act
        get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=duration_seconds,
        )

        # Assert -- verify .convert() was called with correct kwargs
        call_kwargs = mock_client.text_to_sound_effects.convert.call_args.kwargs
        assert call_kwargs["text"] == description
        assert call_kwargs["duration_seconds"] == duration_seconds

    def test_creates_sfx_directory_if_missing(self, tmp_path: Path) -> None:
        """get_sound_effect() creates output_dir/sfx/ if it doesn't exist."""
        # Arrange
        description = "test sound"
        output_dir = tmp_path
        sfx_dir = output_dir / "sfx"
        assert not sfx_dir.exists()

        mock_client = Mock()
        mock_client.text_to_sound_effects.convert.return_value = iter(
            [b"test_audio"]
        )

        # Act
        result = get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
            duration_seconds=2.0,
        )

        # Assert
        assert result is not None
        assert sfx_dir.exists()
        assert result.parent == sfx_dir

    def test_default_duration_is_two_seconds(self, tmp_path: Path) -> None:
        """get_sound_effect() defaults to 2.0 seconds duration when not specified."""
        # Arrange
        description = "default duration test"
        output_dir = tmp_path
        mock_client = Mock()
        mock_client.text_to_sound_effects.convert.return_value = iter(
            [b"audio_data"]
        )

        # Act -- call without specifying duration_seconds
        get_sound_effect(
            description=description,
            output_dir=output_dir,
            client=mock_client,
        )

        # Assert -- verify 2.0 was passed to .convert()
        call_kwargs = mock_client.text_to_sound_effects.convert.call_args.kwargs
        assert call_kwargs["duration_seconds"] == 2.0
