"""Main audio combiner using strategy pattern."""
from pathlib import Path
from typing import List
from .combiner_strategy import CombinerStrategy
from .simple_concat_strategy import SimpleConcatStrategy


class AudioCombiner:
    """
    Audio combiner using strategy pattern.

    Delegates the actual combining to a CombinerStrategy implementation.
    """

    def __init__(self, strategy: CombinerStrategy = None):
        """
        Initialize audio combiner.

        Args:
            strategy: The combining strategy to use (defaults to SimpleConcatStrategy)
        """
        self.strategy = strategy or SimpleConcatStrategy()

    def set_strategy(self, strategy: CombinerStrategy) -> None:
        """
        Change the combining strategy at runtime.

        Args:
            strategy: New strategy to use
        """
        self.strategy = strategy

    def combine_segments(self, segment_files: List[Path], output_file: Path) -> None:
        """
        Combine multiple audio files into one using the current strategy.

        Args:
            segment_files: List of audio file paths in order
            output_file: Path for the combined output file
        """
        self.strategy.combine(segment_files, output_file)
