"""Tests for Suno AI music provider."""
import hashlib
from unittest.mock import Mock, patch

import pytest

from src.audio.suno_music_provider import SunoMusicProvider


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch("src.audio.suno_music_provider.requests") as mock:
        yield mock


@pytest.fixture
def mock_time():
    """Mock time.sleep to avoid actual delays in tests."""
    with patch("src.audio.suno_music_provider.time.sleep"):
        yield


def test_suno_generate_success(mock_requests, mock_time, tmp_path):
    """Test successful music generation with polling."""
    # Arrange
    # Mock submit response
    submit_response = Mock()
    submit_response.json.return_value = {"id": "task_123"}
    submit_response.status_code = 200

    # Mock poll response (complete immediately)
    poll_response = Mock()
    poll_response.json.return_value = {"status": "complete"}
    poll_response.status_code = 200

    # Mock download response
    download_response = Mock()
    download_response.content = b"fake music mp3 data"
    download_response.status_code = 200

    mock_requests.post.return_value = submit_response
    mock_requests.get.side_effect = [poll_response, download_response]

    cache_dir = tmp_path / "cache"
    provider = SunoMusicProvider(api_key="test-key", cache_dir=cache_dir)

    output_path = tmp_path / "test.mp3"

    # Act
    result = provider.generate(
        prompt="uplifting orchestral",
        output_path=output_path,
        duration_seconds=60.0,
    )

    # Assert
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake music mp3 data"

    # Check cache file exists
    prompt_hash = hashlib.sha256(b"uplifting orchestral").hexdigest()
    cache_file = cache_dir / f"{prompt_hash}.mp3"
    assert cache_file.exists()


def test_suno_cache_hit(tmp_path):
    """Test cache hit avoids API calls."""
    # Arrange
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    prompt = "uplifting orchestral"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_file = cache_dir / f"{prompt_hash}.mp3"
    cache_file.write_bytes(b"cached music")

    provider = SunoMusicProvider(api_key="test-key", cache_dir=cache_dir)
    output_path = tmp_path / "output.mp3"

    # Act
    with patch("src.audio.suno_music_provider.requests") as mock_requests:
        result = provider.generate(
            prompt=prompt,
            output_path=output_path,
            duration_seconds=60.0,
        )

        # Assert
        assert result == output_path
        assert output_path.read_bytes() == b"cached music"
        mock_requests.post.assert_not_called()
        mock_requests.get.assert_not_called()


def test_suno_task_timeout(mock_requests, tmp_path):
    """Test timeout returns None after max wait time."""
    # Arrange
    submit_response = Mock()
    submit_response.json.return_value = {"id": "task_123"}
    submit_response.status_code = 200

    # Mock poll response always returns processing
    poll_response = Mock()
    poll_response.json.return_value = {"status": "processing"}
    poll_response.status_code = 200

    mock_requests.post.return_value = submit_response
    mock_requests.get.return_value = poll_response

    cache_dir = tmp_path / "cache"
    provider = SunoMusicProvider(api_key="test-key", cache_dir=cache_dir)
    # Override timeout for testing
    provider._timeout = 1  # 1 second timeout

    output_path = tmp_path / "test.mp3"

    # Act
    with patch("src.audio.suno_music_provider.time.sleep"):
        with patch("src.audio.suno_music_provider.time.time") as mock_time:
            # Simulate time passing
            mock_time.side_effect = [0, 0.5, 1.5]  # Start, first poll, second poll (timeout)
            result = provider.generate(
                prompt="test music",
                output_path=output_path,
            )

    # Assert
    assert result is None
    assert not output_path.exists()


def test_suno_task_failed(mock_requests, mock_time, tmp_path):
    """Test failed task returns None."""
    # Arrange
    submit_response = Mock()
    submit_response.json.return_value = {"id": "task_123"}
    submit_response.status_code = 200

    poll_response = Mock()
    poll_response.json.return_value = {"status": "failed"}
    poll_response.status_code = 200

    mock_requests.post.return_value = submit_response
    mock_requests.get.return_value = poll_response

    cache_dir = tmp_path / "cache"
    provider = SunoMusicProvider(api_key="test-key", cache_dir=cache_dir)

    output_path = tmp_path / "test.mp3"

    # Act
    result = provider.generate(
        prompt="test music",
        output_path=output_path,
    )

    # Assert
    assert result is None
    assert not output_path.exists()


def test_suno_empty_api_key_raises_valueerror(tmp_path):
    """Test empty API key raises ValueError."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="API key cannot be empty"):
        SunoMusicProvider(api_key="", cache_dir=tmp_path)


def test_suno_creates_cache_dir(mock_requests, mock_time, tmp_path):
    """Test cache directory is created if it doesn't exist."""
    # Arrange
    submit_response = Mock()
    submit_response.json.return_value = {"id": "task_123"}
    submit_response.status_code = 200

    poll_response = Mock()
    poll_response.json.return_value = {"status": "complete"}
    poll_response.status_code = 200

    download_response = Mock()
    download_response.content = b"audio"
    download_response.status_code = 200

    mock_requests.post.return_value = submit_response
    mock_requests.get.side_effect = [poll_response, download_response]

    cache_dir = tmp_path / "nonexistent" / "cache"
    provider = SunoMusicProvider(api_key="test-key", cache_dir=cache_dir)

    output_path = tmp_path / "test.mp3"

    # Act
    provider.generate(
        prompt="test music",
        output_path=output_path,
    )

    # Assert
    assert cache_dir.exists()
