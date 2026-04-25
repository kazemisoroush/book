"""Interface for sound effect providers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.domain.models import Beat


class SoundEffectProvider(ABC):
    """Abstract base class for sound effect generation providers.

    Sound effect providers generate discrete event sounds from natural-language
    descriptions (e.g., "dry cough", "firm knock on wooden door").
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this provider (e.g. ``"elevenlabs"``).

        Used to namespace cached artifacts on disk.
        """

    @abstractmethod
    def provide(self, beat: Beat, book_id: str) -> float:
        """Generate a sound effect for a beat.

        Constructs the output path, creates directories, calls generate(),
        measures duration, and sets ``beat.audio_path``.

        Args:
            beat: The beat to generate a sound effect for.
            book_id: The book identifier (used for output path construction).

        Returns:
            Duration of the generated audio in seconds.
        """

    @abstractmethod
    def _generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate a sound effect from description (internal).

        Args:
            description: Natural-language description of the sound effect.
            output_path: Path where the generated audio file should be saved.
            duration_seconds: Desired duration of the effect in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        pass
