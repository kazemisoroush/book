"""Tests for Fish Audio TTS provider."""
from unittest.mock import Mock, patch

import pytest
import requests

from src.tts.fish_audio_tts_provider import FishAudioTTSProvider


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch("src.tts.fish_audio_tts_provider.requests") as mock:
        yield mock


def test_fish_audio_synthesize_success(mock_requests, tmp_path):
    """Test successful synthesis writes audio to output path."""
    # Arrange
    audio_content = b"fake mp3 audio data"
    mock_response = Mock()
    mock_response.content = audio_content
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    provider = FishAudioTTSProvider(api_key="test-key")
    output_path = tmp_path / "test.mp3"

    # Act
    result = provider.synthesize(
        text="Hello world",
        voice_id="voice_123",
        output_path=output_path,
    )

    # Assert
    assert output_path.exists()
    assert output_path.read_bytes() == audio_content
    assert result is None  # Fish Audio doesn't provide request IDs


def test_fish_audio_synthesize_with_speed(mock_requests, tmp_path):
    """Test voice_speed parameter passed to API."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    provider = FishAudioTTSProvider(api_key="test-key")
    output_path = tmp_path / "test.mp3"

    # Act
    provider.synthesize(
        text="Hello",
        voice_id="voice_123",
        output_path=output_path,
        voice_speed=1.5,
    )

    # Assert
    call_args = mock_requests.post.call_args
    json_body = call_args.kwargs["json"]
    assert json_body["speed"] == 1.5


def test_fish_audio_synthesize_ignores_unsupported_params(mock_requests, tmp_path):
    """Test unsupported parameters are ignored gracefully."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response

    provider = FishAudioTTSProvider(api_key="test-key")
    output_path = tmp_path / "test.mp3"

    # Act
    result = provider.synthesize(
        text="Hello",
        voice_id="voice_123",
        output_path=output_path,
        previous_text="Previous sentence",
        next_text="Next sentence",
        voice_stability=0.5,
        voice_style=0.3,
        previous_request_ids=["id1", "id2"],
    )

    # Assert - synthesis succeeds despite unsupported params
    assert output_path.exists()
    assert result is None


def test_fish_audio_api_failure_returns_none(tmp_path):
    """Test API failure returns None and logs warning."""
    # Arrange
    with patch("src.tts.fish_audio_tts_provider.requests") as mock_requests:
        mock_requests.post.side_effect = requests.RequestException("API error")
        mock_requests.RequestException = requests.RequestException  # Patch the exception class too

        provider = FishAudioTTSProvider(api_key="test-key")
        output_path = tmp_path / "test.mp3"

        # Act
        result = provider.synthesize(
            text="Hello",
            voice_id="voice_123",
            output_path=output_path,
        )

        # Assert
        assert result is None
        assert not output_path.exists()


def test_fish_audio_empty_api_key_raises_valueerror():
    """Test empty API key raises ValueError."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="API key cannot be empty"):
        FishAudioTTSProvider(api_key="")


def test_fish_audio_get_voices_caches_result(mock_requests):
    """Test voice list is cached after first call."""
    # Arrange
    mock_response = Mock()
    mock_response.json.return_value = {
        "voices": [
            {"id": "voice1", "name": "Voice One"},
            {"id": "voice2", "name": "Voice Two"},
        ]
    }
    mock_response.status_code = 200
    mock_requests.get.return_value = mock_response

    provider = FishAudioTTSProvider(api_key="test-key")

    # Act
    voices1 = provider.get_available_voices()
    voices2 = provider.get_available_voices()

    # Assert
    assert voices1 == {"Voice One": "voice1", "Voice Two": "voice2"}
    assert voices1 == voices2
    mock_requests.get.assert_called_once()  # Only one API call
