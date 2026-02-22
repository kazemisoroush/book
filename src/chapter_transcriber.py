"""Chapter transcript writer for debugging."""
from pathlib import Path
from src.domain.models import Chapter


class ChapterTranscriber:
    """Writes chapter text content to a transcript file."""

    def write_transcript(self, chapter: Chapter, output_file: Path) -> None:
        """
        Write chapter transcript to a text file with speaker annotations.

        Args:
            chapter: The chapter to transcribe
            output_file: Path where the transcript will be written
        """
        lines = []

        for segment in chapter.segments:
            # Add speaker header
            if segment.is_dialogue():
                if segment.speaker:
                    lines.append(f"[{segment.speaker}]")
                else:
                    lines.append("[Unknown Speaker]")
            else:
                lines.append("[NARRATION]")

            # Add the text
            lines.append(segment.text)
            lines.append("")  # Blank line between segments

        output_file.write_text("\n".join(lines))
