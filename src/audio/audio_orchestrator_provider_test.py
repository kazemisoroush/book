"""Tests for AudioOrchestrator provider injection."""
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.audio_orchestrator import AudioOrchestrator
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider


class MockSoundEffectProvider(SoundEffectProvider):
    """Mock sound effect provider for testing."""

    def __init__(self) -> None:
        self.generate_called = False
        self.last_description: str | None = None

    def provide(self, segment: object, book_id: str) -> float:
        return 0.0

    def _generate(
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

    def provide(self, scene: object, book_id: str) -> float:
        return 0.0

    def _generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        self.generate_called = True
        self.last_prompt = prompt
        return output_path


class TestAudioOrchestratorProviderInjection:
    """Test that AudioOrchestrator accepts optional providers."""

    def test_accepts_sound_effect_provider(self) -> None:
        # Arrange
        tts_provider = MagicMock()
        sfx_provider = MockSoundEffectProvider()

        # Act
        orchestrator = AudioOrchestrator(
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
        orchestrator = AudioOrchestrator(
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
        orchestrator = AudioOrchestrator(
            tts_provider,
            output_dir=Path("/tmp"),
        )

        # Assert
        assert orchestrator._sound_effect_provider is None
        assert orchestrator._ambient_provider is None

