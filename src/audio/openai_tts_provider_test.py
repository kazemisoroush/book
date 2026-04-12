"""Tests for OpenAI TTS provider."""
from unittest.mock import Mock

import pytest

from src.audio.openai_tts_provider import OpenAITTSProvider


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    client = Mock()
    client.audio = Mock()
    client.audio.speech = Mock()
    return client


def test_openai_synthesize_success(mock_openai_client, tmp_path):
    """Test successful synthesis writes audio to output path."""
    # Arrange
    audio_content = b"fake mp3 audio data"
    mock_response = Mock()
    mock_response.content = audio_content
    mock_openai_client.audio.speech.create.return_value = mock_response

    provider = OpenAITTSProvider(api_key="test-key", model="tts-1")
    provider._client = mock_openai_client

    output_path = tmp_path / "test.mp3"

    # Act
    result = provider.synthesize(
        text="Hello world",
        voice_id="alloy",
        output_path=output_path,
    )

    # Assert
    assert output_path.exists()
    assert output_path.read_bytes() == audio_content
    assert result is None  # OpenAI doesn't provide request IDs


def test_openai_voice_clamping(mock_openai_client, tmp_path):
    """Test invalid voice_id defaults to alloy with warning."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_openai_client.audio.speech.create.return_value = mock_response

    provider = OpenAITTSProvider(api_key="test-key")
    provider._client = mock_openai_client

    output_path = tmp_path / "test.mp3"

    # Act
    provider.synthesize(
        text="Hello",
        voice_id="invalid_voice",
        output_path=output_path,
    )

    # Assert
    call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
    assert call_kwargs["voice"] == "alloy"


def test_openai_speed_clamping(mock_openai_client, tmp_path):
    """Test voice_speed is clamped to valid range 0.25-4.0."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_openai_client.audio.speech.create.return_value = mock_response

    provider = OpenAITTSProvider(api_key="test-key")
    provider._client = mock_openai_client

    output_path = tmp_path / "test.mp3"

    # Act - test upper bound
    provider.synthesize(
        text="Hello",
        voice_id="alloy",
        output_path=output_path,
        voice_speed=5.0,  # Above max
    )

    # Assert
    call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
    assert call_kwargs["speed"] == 4.0

    # Act - test lower bound
    provider.synthesize(
        text="Hello",
        voice_id="alloy",
        output_path=output_path,
        voice_speed=0.1,  # Below min
    )

    # Assert
    call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
    assert call_kwargs["speed"] == 0.25


def test_openai_speed_omitted_when_none(mock_openai_client, tmp_path):
    """Test speed parameter omitted from request when None."""
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_openai_client.audio.speech.create.return_value = mock_response

    provider = OpenAITTSProvider(api_key="test-key")
    provider._client = mock_openai_client

    output_path = tmp_path / "test.mp3"

    # Act
    provider.synthesize(
        text="Hello",
        voice_id="alloy",
        output_path=output_path,
        voice_speed=None,
    )

    # Assert
    call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
    assert "speed" not in call_kwargs


def test_openai_empty_api_key_raises_valueerror():
    """Test empty API key raises ValueError."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="API key cannot be empty"):
        OpenAITTSProvider(api_key="")


def test_openai_get_voices_returns_hardcoded_dict():
    """Test get_available_voices returns hardcoded 6 voices."""
    # Arrange
    provider = OpenAITTSProvider(api_key="test-key")

    # Act
    voices = provider.get_available_voices()

    # Assert
    assert len(voices) == 6
    assert voices == {
        "alloy": "alloy",
        "echo": "echo",
        "fable": "fable",
        "onyx": "onyx",
        "nova": "nova",
        "shimmer": "shimmer",
    }
