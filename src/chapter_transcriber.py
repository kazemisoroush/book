"""Chapter transcript writer for debugging."""
from pathlib import Path
from src.domain.models import Chapter


class ChapterTranscriber:
    """Writes chapter text content to a transcript file."""

    def write_transcript(self, chapter: Chapter, output_file: Path) -> None:
        """
        Write chapter transcript to a text file.

        Args:
            chapter: The chapter to transcribe
            output_file: Path where the transcript will be written
        """
        lines = []
        lines.append(f"=== {chapter.title} ===\n")

        for i, segment in enumerate(chapter.segments):
            # Add segment header
            if segment.is_dialogue():
                if segment.speaker:
                    lines.append(f"\n[DIALOGUE - {segment.speaker}]")
                else:
                    lines.append(f"\n[DIALOGUE]")
            else:
                lines.append(f"\n[NARRATION]")

            # Add segment text
            lines.append(segment.text)

        output_file.write_text("\n".join(lines))
