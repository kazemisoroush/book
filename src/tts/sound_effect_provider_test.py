"""Tests for SoundEffectProvider ABC."""
from pathlib import Path
from typing import Optional
import pytest

from src.tts.sound_effect_provider import SoundEffectProvider


class ConcreteSoundEffectProvider(SoundEffectProvider):
    """Minimal concrete implementation for testing."""

    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        return output_path


class TestSoundEffectProviderABC:
    """Test that SoundEffectProvider enforces the abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            SoundEffectProvider()  # type: ignore

    def test_concrete_implementation_can_be_instantiated(self) -> None:
        # Arrange / Act
        provider = ConcreteSoundEffectProvider()

        # Assert
        assert provider is not None

    def test_generate_returns_optional_path(self) -> None:
        # Arrange
        provider = ConcreteSoundEffectProvider()
        output_path = Path("/tmp/test.mp3")

        # Act
        result = provider.generate("test description", output_path)

        # Assert
        assert result == output_path
