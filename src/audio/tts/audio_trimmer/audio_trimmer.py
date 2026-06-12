"""Abstract base for audio-side beat trimmers."""
from abc import ABC, abstractmethod
from pathlib import Path


class AudioTrimmer(ABC):
    """One-purpose transform from one beat audio file into another."""

    @abstractmethod
    def trim(self, input_path: Path, output_path: Path) -> Path:
        """Apply this transform to *input_path*; write the result to *output_path*."""
