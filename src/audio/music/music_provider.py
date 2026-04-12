"""Interface for music generation providers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class MusicProvider(ABC):
    """Abstract base class for music generation providers.

    Music providers generate background music tracks from mood/style prompts
    (e.g., "uplifting orchestral", "tense thriller score").
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate music from mood/style prompt.

        Args:
            prompt: Natural-language description of the desired music mood/style.
            output_path: Path where the generated audio file should be saved.
            duration_seconds: Desired duration of the music track in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        pass
