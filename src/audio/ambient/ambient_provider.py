"""Interface for ambient audio providers."""
from abc import ABC, abstractmethod

from src.domain.models import Scene


class AmbientProvider(ABC):
    """Abstract base class for ambient audio generation providers.

    Ambient providers generate environmental background audio from natural-language
    prompts (e.g., "gentle forest sounds with distant birds", "busy city street").
    The generated audio should be loopable for mixing under speech.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this provider (e.g. ``"elevenlabs"``).

        Used to namespace generated artifacts on disk.
        """

    @abstractmethod
    def provide(self, scene: Scene, book_id: str) -> float:
        """Generate ambient audio for a scene.

        Writes to ``books_dir/<book_id>/audio/ambient/<provider>/<scene.scene_id>.mp3``
        and skips the underlying API call when the file already exists.

        Args:
            scene: The scene to generate ambient audio for.
            book_id: The book identifier (used for output path construction).

        Returns:
            Duration of the generated audio in seconds.
        """
