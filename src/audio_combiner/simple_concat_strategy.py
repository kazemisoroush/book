"""Simple concatenation strategy using ffmpeg concat demuxer."""
import subprocess
from pathlib import Path
from typing import List
from .combiner_strategy import CombinerStrategy


class SimpleConcatStrategy(CombinerStrategy):
    """
    Simple concatenation using ffmpeg concat demuxer.

    Fast, lossless, no re-encoding.
    Best for audiobooks with natural pauses between segments.
    """

    def combine(self, segment_files: List[Path], output_file: Path) -> None:
        """
        Combine audio files using ffmpeg concat demuxer.

        This is the fastest method - no re-encoding, just stream copying.

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

        # Create a temporary file list for ffmpeg concat
        concat_file = output_file.parent / f"{output_file.stem}_concat.txt"

        try:
            # Write the list of files for ffmpeg
            with open(concat_file, 'w', encoding='utf-8') as f:
                for segment_file in segment_files:
                    # ffmpeg concat requires: file 'path'
                    # Use absolute paths to avoid issues
                    abs_path = segment_file.resolve()
                    f.write(f"file '{abs_path}'\n")

            # Run ffmpeg to concatenate
            result = subprocess.run(
                [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_file),
                    '-c', 'copy',  # Stream copy - no re-encoding!
                    '-y',  # Overwrite output file
                    str(output_file)
                ],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        finally:
            # Clean up the concat file
            concat_file.unlink(missing_ok=True)
