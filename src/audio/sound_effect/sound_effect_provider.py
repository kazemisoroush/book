"""Interface for sound effect providers."""
from abc import ABC, abstractmethod

from src.domain.beat import Beat


class SoundEffectProvider(ABC):
    """Abstract base class for sound effect generation providers.

    Sound effect providers generate discrete event sounds from natural-language
    descriptions (e.g., "dry cough", "firm knock on wooden door").
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this provider (e.g. ``"elevenlabs"``).

        Used to namespace generated artifacts on disk.
        """

    @abstractmethod
    def provide(self, beat: Beat, book_id: str) -> float:
        """Generate a sound effect for a beat.

        Writes to ``books_dir/<book_id>/audio/sfx/<provider>/beat_NNNN.mp3``
        (counter scoped per provider instance) and skips the underlying API
        call when the file already exists.

        Args:
            beat: The beat to generate a sound effect for.
            book_id: The book identifier (used for output path construction).

        Returns:
            Duration of the generated audio in seconds.
        """
