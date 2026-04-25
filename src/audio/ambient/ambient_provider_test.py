"""Tests for AmbientProvider ABC."""
from pathlib import Path
from typing import Optional

from src.audio.ambient.ambient_provider import AmbientProvider


class ConcreteAmbientProvider(AmbientProvider):
    """Minimal concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "concrete"

    def provide(self, scene: object, book_id: str) -> float:
        return 0.0

    def _generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        return output_path


class TestAmbientProviderABC:
    """Test that AmbientProvider enforces the abstract interface."""

    def test_generate_returns_optional_path(self) -> None:
        # Arrange
        provider = ConcreteAmbientProvider()
        output_path = Path("/tmp/ambient.mp3")

        # Act
        result = provider._generate("ambient prompt", output_path)

        # Assert
        assert result == output_path
