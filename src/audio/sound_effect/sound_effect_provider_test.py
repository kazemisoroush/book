"""Tests for SoundEffectProvider ABC."""
from pathlib import Path
from typing import Optional

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider


class ConcreteSoundEffectProvider(SoundEffectProvider):
    """Minimal concrete implementation for testing."""

    def provide(self, segment: object, book_id: str) -> float:
        return 0.0

    def _generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        return output_path


class TestSoundEffectProviderABC:
    """Test that SoundEffectProvider enforces the abstract interface."""

    def test_generate_returns_optional_path(self) -> None:
        # Arrange
        provider = ConcreteSoundEffectProvider()
        output_path = Path("/tmp/test.mp3")

        # Act
        result = provider._generate("test description", output_path)

        # Assert
        assert result == output_path
