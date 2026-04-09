"""Tests for MusicProvider ABC."""
from pathlib import Path
from typing import Optional
import pytest

from src.tts.music_provider import MusicProvider


class ConcreteMusicProvider(MusicProvider):
    """Minimal concrete implementation for testing."""

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        return output_path


class TestMusicProviderABC:
    """Test that MusicProvider enforces the abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            MusicProvider()  # type: ignore

    def test_concrete_implementation_can_be_instantiated(self) -> None:
        # Arrange / Act
        provider = ConcreteMusicProvider()

        # Assert
        assert provider is not None

    def test_generate_returns_optional_path(self) -> None:
        # Arrange
        provider = ConcreteMusicProvider()
        output_path = Path("/tmp/music.mp3")

        # Act
        result = provider.generate("uplifting orchestral", output_path)

        # Assert
        assert result == output_path
