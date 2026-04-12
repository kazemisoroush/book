"""Interface for ambient audio providers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class AmbientProvider(ABC):
    """Abstract base class for ambient audio generation providers.

    Ambient providers generate environmental background audio from natural-language
    prompts (e.g., "gentle forest sounds with distant birds", "busy city street").
    The generated audio should be loopable for mixing under speech.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate ambient audio from natural-language prompt.

        Args:
            prompt: Natural-language description of the ambient environment.
            output_path: Path where the generated audio file should be saved.
            duration_seconds: Desired duration of the ambient clip in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        pass
