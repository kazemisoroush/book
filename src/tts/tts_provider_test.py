"""Tests for TTSProvider interface."""
from pathlib import Path
from typing import Any, Optional

import pytest

from src.tts.tts_provider import TTSProvider


class MinimalTTSProvider(TTSProvider):
    """Minimal concrete implementation for testing."""

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Minimal implementation."""
        return None

    def get_available_voices(self) -> dict[str, str]:
        """Minimal implementation."""
        return {}

    def get_voices(self) -> list[dict[str, Any]]:
        """Minimal implementation."""
        return []


class TestTTSProviderGetVoicesAbstractMethod:
    """Tests for get_voices() abstract method."""

    def test_get_voices_is_abstract(self) -> None:
        """Attempting to instantiate TTSProvider without get_voices() must fail."""
        # Arrange & Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class IncompleteProvider(TTSProvider):
                def synthesize(
                    self,
                    text: str,
                    voice_id: str,
                    output_path: Path,
                    emotion: Optional[str] = None,
                    previous_text: Optional[str] = None,
                    next_text: Optional[str] = None,
                    voice_stability: Optional[float] = None,
                    voice_style: Optional[float] = None,
                    voice_speed: Optional[float] = None,
                    previous_request_ids: Optional[list[str]] = None,
                ) -> Optional[str]:
                    return None

                def get_available_voices(self) -> dict[str, str]:
                    return {}

                # Missing get_voices()

            IncompleteProvider()  # type: ignore[abstract]

    def test_get_voices_returns_list_of_dicts(self) -> None:
        """get_voices() must return a list of dictionaries."""
        # Arrange
        provider = MinimalTTSProvider()

        # Act
        result = provider.get_voices()

        # Assert
        assert isinstance(result, list)
