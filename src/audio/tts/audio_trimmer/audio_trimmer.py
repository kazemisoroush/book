"""Abstract base for audio-side beat trimmers."""
from abc import ABC, abstractmethod
from pathlib import Path


class AudioTrimmer(ABC):
    """One-purpose transform from one beat audio file into another."""

    def trim(self, input_path: Path, output_path: Path) -> Path:
        """Skip if *output_path* already holds a valid result; otherwise transform."""
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        return self._trim(input_path, output_path)

    @abstractmethod
    def _trim(self, input_path: Path, output_path: Path) -> Path:
        """Apply this transform to *input_path* and write the result to *output_path*."""
