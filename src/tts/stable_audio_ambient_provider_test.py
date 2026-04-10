"""Tests for Stable Audio ambient provider."""
import hashlib
from unittest.mock import Mock, patch

import pytest
import requests

from src.tts.stable_audio_ambient_provider import StableAudioAmbientProvider


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch("src.tts.stable_audio_ambient_provider.requests") as mock:
        yield mock


def test_stable_audio_ambient_generate_success(mock_requests, tmp_path):
    """Test successful generation writes audio to output path and cache."""
    # Arrange
    audio_content = b"fake mp3 ambient audio"
    mock_response = Mock()
    mock_response.content = audio_content
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    cache_dir = tmp_path / "cache"
    provider = StableAudioAmbientProvider(api_key="test-key", cache_dir=cache_dir)

    output_path = tmp_path / "test.mp3"

    # Act
    result = provider.generate(
        prompt="forest sounds with birds",
        output_path=output_path,
        duration_seconds=60.0,
    )

    # Assert
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_bytes() == audio_content

    # Check cache file exists
    prompt_hash = hashlib.sha256(b"forest sounds with birds").hexdigest()
    cache_file = cache_dir / f"{prompt_hash}.mp3"
    assert cache_file.exists()


def test_stable_audio_ambient_cache_hit(tmp_path):
    """Test cache hit avoids API call."""
    # Arrange
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    prompt = "forest sounds"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_file = cache_dir / f"{prompt_hash}.mp3"
    cache_file.write_bytes(b"cached ambient audio")

    provider = StableAudioAmbientProvider(api_key="test-key", cache_dir=cache_dir)
    output_path = tmp_path / "output.mp3"

    # Act
    with patch("src.tts.stable_audio_ambient_provider.requests") as mock_requests:
        result = provider.generate(
            prompt=prompt,
            output_path=output_path,
            duration_seconds=60.0,
        )

        # Assert
        assert result == output_path
        assert output_path.read_bytes() == b"cached ambient audio"
        mock_requests.post.assert_not_called()


def test_stable_audio_ambient_api_failure_returns_none(tmp_path):
    """Test API failure returns None and logs warning."""
    # Arrange
    with patch("src.tts.stable_audio_ambient_provider.requests") as mock_requests:
        mock_requests.post.side_effect = requests.RequestException("API error")
        mock_requests.RequestException = requests.RequestException

        cache_dir = tmp_path / "cache"
        provider = StableAudioAmbientProvider(api_key="test-key", cache_dir=cache_dir)

        output_path = tmp_path / "test.mp3"

        # Act
        result = provider.generate(
            prompt="forest sounds",
            output_path=output_path,
        )

        # Assert
        assert result is None


def test_stable_audio_ambient_empty_api_key_raises_valueerror(tmp_path):
    """Test empty API key raises ValueError."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="API key cannot be empty"):
        StableAudioAmbientProvider(api_key="", cache_dir=tmp_path)


def test_stable_audio_ambient_creates_cache_dir(mock_requests, tmp_path):
    """Test cache directory is created if it doesn't exist."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    cache_dir = tmp_path / "nonexistent" / "cache"
    provider = StableAudioAmbientProvider(api_key="test-key", cache_dir=cache_dir)

    output_path = tmp_path / "test.mp3"

    # Act
    provider.generate(
        prompt="test ambient",
        output_path=output_path,
    )

    # Assert
    assert cache_dir.exists()
