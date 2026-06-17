"""Tests for Fish Audio TTS provider."""
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.domain.beat import Beat, BeatType
from src.domain.models import Chapter


def _beat(text: str, voice_id: str | None = "voice_123") -> Beat:
    return Beat(text=text, beat_type=BeatType.NARRATION, character_id=1, voice_id=voice_id)


@pytest.fixture
def mock_requests():
    """Patch the requests module used by FishAudioTTSProvider."""
    with patch("src.audio.tts.fish_audio_tts_provider.requests") as mock:
        yield mock


def test_fish_audio_provide_writes_audio_under_book_dir(
    mock_requests: Mock, tmp_path: Path,
) -> None:
    # Arrange
    audio_content = b"fake mp3 audio data"
    mock_response = Mock()
    mock_response.content = audio_content
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    provider = FishAudioTTSProvider(api_key="test-key", books_dir=tmp_path)

    # Act
    result = provider.provide(_beat("Hello world"), "book")

    # Assert
    output_path = tmp_path / "book" / "audio" / "tts" / "fish_audio" / "beat_0001.mp3"
    assert output_path.exists()
    assert output_path.read_bytes() == audio_content
    assert result is None


def test_fish_audio_provide_collection_calls_post_once_per_beat(
    mock_requests: Mock, tmp_path: Path,
) -> None:
    # Arrange
    mock_response = Mock()
    mock_response.content = b"audio"
    mock_response.status_code = 200
    mock_requests.post.return_value = mock_response
    provider = FishAudioTTSProvider(api_key="test-key", books_dir=tmp_path)
    beats = [_beat("Hello"), _beat("World")]

    # Act
    provider.provide_collection(Chapter(number=1, title='', beats=beats), "book")

    # Assert
    assert mock_requests.post.call_count == 2


def test_fish_audio_api_failure_returns_none(tmp_path: Path) -> None:
    # Arrange
    with patch("src.audio.tts.fish_audio_tts_provider.requests") as mock_requests:
        mock_requests.post.side_effect = requests.RequestException("API error")
        mock_requests.RequestException = requests.RequestException
        provider = FishAudioTTSProvider(api_key="test-key", books_dir=tmp_path)

        # Act
        result = provider.provide(_beat("Hello"), "book")

        # Assert
        assert result is None
        assert not list(tmp_path.rglob("*.mp3"))


def test_fish_audio_empty_api_key_raises_valueerror() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="API key cannot be empty"):
        FishAudioTTSProvider(api_key="")
