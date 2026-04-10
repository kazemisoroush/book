"""Tests for FallbackTTSProvider wrapper."""
from unittest.mock import Mock

import pytest

from src.tts.fallback_tts_provider import FallbackTTSProvider


@pytest.fixture
def mock_primary():
    """Create a mock primary TTS provider."""
    provider = Mock()
    provider.synthesize = Mock()
    provider.get_available_voices = Mock(return_value={"voice1": "id1"})
    provider.get_voices = Mock(return_value=[])
    return provider


@pytest.fixture
def mock_fallback():
    """Create a mock fallback TTS provider."""
    provider = Mock()
    provider.synthesize = Mock()
    provider.get_available_voices = Mock(return_value={"voice2": "id2"})
    provider.get_voices = Mock(return_value=[])
    return provider


def test_fallback_primary_success(mock_primary, mock_fallback, tmp_path):
    """Test fallback not called when primary succeeds."""
    # Arrange
    mock_primary.synthesize.return_value = "request_123"
    wrapper = FallbackTTSProvider(primary=mock_primary, fallback=mock_fallback)

    output_path = tmp_path / "test.mp3"

    # Act
    result = wrapper.synthesize(
        text="Hello",
        voice_id="voice1",
        output_path=output_path,
    )

    # Assert
    assert result == "request_123"
    mock_primary.synthesize.assert_called_once()
    mock_fallback.synthesize.assert_not_called()


def test_fallback_primary_fails_fallback_succeeds(mock_primary, mock_fallback, tmp_path):
    """Test fallback called when primary raises exception."""
    # Arrange
    mock_primary.synthesize.side_effect = Exception("Primary failed")
    mock_fallback.synthesize.return_value = None

    wrapper = FallbackTTSProvider(primary=mock_primary, fallback=mock_fallback)

    output_path = tmp_path / "test.mp3"

    # Act
    result = wrapper.synthesize(
        text="Hello",
        voice_id="voice1",
        output_path=output_path,
    )

    # Assert
    assert result is None
    mock_primary.synthesize.assert_called_once()
    mock_fallback.synthesize.assert_called_once()


def test_fallback_both_fail(mock_primary, mock_fallback, tmp_path):
    """Test exception re-raised when both primary and fallback fail."""
    # Arrange
    mock_primary.synthesize.side_effect = Exception("Primary failed")
    mock_fallback.synthesize.side_effect = Exception("Fallback failed")

    wrapper = FallbackTTSProvider(primary=mock_primary, fallback=mock_fallback)

    output_path = tmp_path / "test.mp3"

    # Act & Assert
    with pytest.raises(Exception, match="Fallback failed"):
        wrapper.synthesize(
            text="Hello",
            voice_id="voice1",
            output_path=output_path,
        )


def test_fallback_get_voices_delegates_to_primary(mock_primary, mock_fallback):
    """Test get_available_voices delegates to primary only."""
    # Arrange
    wrapper = FallbackTTSProvider(primary=mock_primary, fallback=mock_fallback)

    # Act
    voices = wrapper.get_available_voices()

    # Assert
    assert voices == {"voice1": "id1"}
    mock_primary.get_available_voices.assert_called_once()
    mock_fallback.get_available_voices.assert_not_called()
