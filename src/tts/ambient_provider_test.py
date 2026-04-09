"""Tests for AmbientProvider ABC."""
from pathlib import Path
from typing import Optional
import pytest

from src.tts.ambient_provider import AmbientProvider


class ConcreteAmbientProvider(AmbientProvider):
    """Minimal concrete implementation for testing."""

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        return output_path


class TestAmbientProviderABC:
    """Test that AmbientProvider enforces the abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AmbientProvider()  # type: ignore

    def test_concrete_implementation_can_be_instantiated(self) -> None:
        # Arrange / Act
        provider = ConcreteAmbientProvider()

        # Assert
        assert provider is not None

    def test_generate_returns_optional_path(self) -> None:
        # Arrange
        provider = ConcreteAmbientProvider()
        output_path = Path("/tmp/ambient.mp3")

        # Act
        result = provider.generate("ambient prompt", output_path)

        # Assert
        assert result == output_path
