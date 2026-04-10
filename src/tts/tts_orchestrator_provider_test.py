"""Tests for TTSOrchestrator provider injection."""
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock


from src.tts.ambient_provider import AmbientProvider
from src.tts.sound_effect_provider import SoundEffectProvider
from src.tts.tts_orchestrator import TTSOrchestrator


class MockSoundEffectProvider(SoundEffectProvider):
    """Mock sound effect provider for testing."""

    def __init__(self) -> None:
        self.generate_called = False
        self.last_description: str | None = None

    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        self.generate_called = True
        self.last_description = description
        return output_path


class MockAmbientProvider(AmbientProvider):
    """Mock ambient provider for testing."""

    def __init__(self) -> None:
        self.generate_called = False
        self.last_prompt: str | None = None

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        self.generate_called = True
        self.last_prompt = prompt
        return output_path


class TestTTSOrchestratorProviderInjection:
    """Test that TTSOrchestrator accepts optional providers."""

    def test_accepts_sound_effect_provider(self) -> None:
        # Arrange
        tts_provider = MagicMock()
        sfx_provider = MockSoundEffectProvider()

        # Act
        orchestrator = TTSOrchestrator(
            tts_provider,
            output_dir=Path("/tmp"),
            sound_effect_provider=sfx_provider,
        )

        # Assert
        assert orchestrator._sound_effect_provider is sfx_provider

    def test_accepts_ambient_provider(self) -> None:
        # Arrange
        tts_provider = MagicMock()
        ambient_provider = MockAmbientProvider()

        # Act
        orchestrator = TTSOrchestrator(
            tts_provider,
            output_dir=Path("/tmp"),
            ambient_provider=ambient_provider,
        )

        # Assert
        assert orchestrator._ambient_provider is ambient_provider

    def test_providers_default_to_none(self) -> None:
        # Arrange
        tts_provider = MagicMock()

        # Act
        orchestrator = TTSOrchestrator(
            tts_provider,
            output_dir=Path("/tmp"),
        )

        # Assert
        assert orchestrator._sound_effect_provider is None
        assert orchestrator._ambient_provider is None

    def test_backward_compat_clients_create_providers(self) -> None:
        # Arrange
        tts_provider = MagicMock()
        sfx_client = MagicMock()
        ambient_client = MagicMock()

        # Act
        orchestrator = TTSOrchestrator(
            tts_provider,
            output_dir=Path("/tmp"),
            sfx_client=sfx_client,
            ambient_client=ambient_client,
        )

        # Assert - providers should be auto-created from clients
        assert orchestrator._sound_effect_provider is not None
        assert orchestrator._ambient_provider is not None
