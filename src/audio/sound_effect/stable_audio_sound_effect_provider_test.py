"""Tests for Stable Audio sound effect provider."""
import hashlib
from unittest.mock import Mock, patch

import pytest
import requests

from src.audio.sound_effect.stable_audio_sound_effect_provider import (
    StableAudioSoundEffectProvider,
)


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch("src.audio.sound_effect.stable_audio_sound_effect_provider.requests") as mock:
        yield mock


def test_stable_audio_sfx_generate_success(mock_requests, tmp_path):
    """Test successful generation writes audio to output path and cache."""
    # Arrange
    audio_content = b"fake mp3 audio data"
    mock_response = Mock()
    mock_response.content = audio_content
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    provider = StableAudioSoundEffectProvider(api_key="test-key", books_dir=tmp_path)

    output_path = tmp_path / "test.mp3"

    # Act
    result = provider._generate(
        description="door knock",
        output_path=output_path,
        duration_seconds=2.0,
    )

    # Assert
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_bytes() == audio_content

    # Check cache file exists
    desc_hash = hashlib.sha256(b"door knock").hexdigest()
    cache_file = tmp_path / "cache" / "sfx" / f"{desc_hash}.mp3"
    assert cache_file.exists()


def test_stable_audio_sfx_cache_hit(tmp_path):
    """Test cache hit avoids API call."""
    # Arrange
    cache_dir = tmp_path / "cache" / "sfx"
    cache_dir.mkdir(parents=True)

    description = "door knock"
    desc_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
    cache_file = cache_dir / f"{desc_hash}.mp3"
    cache_file.write_bytes(b"cached audio")

    provider = StableAudioSoundEffectProvider(api_key="test-key", books_dir=tmp_path)
    output_path = tmp_path / "output.mp3"

    # Act
    with patch("src.audio.sound_effect.stable_audio_sound_effect_provider.requests") as mock_req:
        result = provider._generate(
            description=description,
            output_path=output_path,
            duration_seconds=2.0,
        )

        # Assert
        assert result == output_path
        assert output_path.read_bytes() == b"cached audio"
        mock_req.post.assert_not_called()


def test_stable_audio_sfx_api_failure_returns_none(tmp_path):
    """Test API failure returns None and logs warning."""
    # Arrange
    with patch("src.audio.sound_effect.stable_audio_sound_effect_provider.requests") as mock_req:
        mock_req.post.side_effect = requests.RequestException("API error")
        mock_req.RequestException = requests.RequestException

        provider = StableAudioSoundEffectProvider(api_key="test-key", books_dir=tmp_path)

        output_path = tmp_path / "test.mp3"

        # Act
        result = provider._generate(
            description="door knock",
            output_path=output_path,
        )

        # Assert
        assert result is None


def test_stable_audio_sfx_empty_api_key_raises_valueerror(tmp_path):
    """Test empty API key raises ValueError."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="API key cannot be empty"):
        StableAudioSoundEffectProvider(api_key="", books_dir=tmp_path)


def test_stable_audio_sfx_creates_cache_dir(mock_requests, tmp_path):
    """Test cache directory is created if it doesn't exist."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    provider = StableAudioSoundEffectProvider(api_key="test-key", books_dir=tmp_path)

    output_path = tmp_path / "test.mp3"

    # Act
    provider._generate(
        description="test",
        output_path=output_path,
    )

    # Assert
    assert (tmp_path / "cache" / "sfx").exists()
