"""Crossfade strategy using ffmpeg audio filters."""
import subprocess
from pathlib import Path
from typing import List
from .combiner_strategy import CombinerStrategy


class CrossfadeStrategy(CombinerStrategy):
    """
    Crossfade strategy using ffmpeg audio filters.

    Creates smooth transitions between segments with overlapping fades.
    Slower than simple concat (requires re-encoding) but smoother transitions.
    """

    def __init__(self, crossfade_duration: float = 0.1):
        """
        Initialize crossfade strategy.

        Args:
            crossfade_duration: Duration of crossfade in seconds (default 0.1s)
        """
        self.crossfade_duration = crossfade_duration

    def combine(self, segment_files: List[Path], output_file: Path) -> None:
        """
        Combine audio files with crossfade between segments.

        Args:
            segment_files: List of audio file paths in order
            output_file: Path for the combined output file
        """
        if not segment_files:
            raise ValueError("No segment files to combine")

        if len(segment_files) == 1:
            # Just copy if there's only one file
            import shutil
            shutil.copy2(segment_files[0], output_file)
            return

        # Build ffmpeg filter complex for crossfading
        filter_parts = []
        current_output = "[0:a]"

        for i in range(1, len(segment_files)):
            next_input = f"[{i}:a]"
            fade_output = f"[a{i}]"

            # acrossfade filter: d=duration, c1/c2=curve (tri=triangular)
            filter_parts.append(
                f"{current_output}{next_input}acrossfade=d={self.crossfade_duration}:c1=tri:c2=tri{fade_output}"
            )
            current_output = fade_output

        filter_complex = ";".join(filter_parts)

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y']

        # Add all input files
        for segment_file in segment_files:
            cmd.extend(['-i', str(segment_file)])

        # Add filter complex
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', current_output,
            str(output_file)
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg crossfade failed: {result.stderr}")
