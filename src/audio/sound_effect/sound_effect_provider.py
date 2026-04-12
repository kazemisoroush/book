"""Interface for sound effect providers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class SoundEffectProvider(ABC):
    """Abstract base class for sound effect generation providers.

    Sound effect providers generate discrete event sounds from natural-language
    descriptions (e.g., "dry cough", "firm knock on wooden door").
    """

    @abstractmethod
    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate a sound effect from description.

        Args:
            description: Natural-language description of the sound effect.
            output_path: Path where the generated audio file should be saved.
            duration_seconds: Desired duration of the effect in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        pass
