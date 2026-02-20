"""Interface for audio combining strategies."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class CombinerStrategy(ABC):
    """Abstract base class for audio combining strategies."""

    @abstractmethod
    def combine(self, segment_files: List[Path], output_file: Path) -> None:
        """
        Combine multiple audio files into one.

        Args:
            segment_files: List of audio file paths in order
            output_file: Path for the combined output file
        """
        pass
