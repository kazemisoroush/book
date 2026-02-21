"""Chapter transcript writer for debugging."""
from pathlib import Path
from src.domain.models import Chapter


class ChapterTranscriber:
    """Writes chapter text content to a transcript file."""

    def write_transcript(self, chapter: Chapter, output_file: Path) -> None:
        """
        Write chapter transcript to a text file.

        Writes exactly what the TTS receives - just the plain text.

        Args:
            chapter: The chapter to transcribe
            output_file: Path where the transcript will be written
        """
        lines = []

        for segment in chapter.segments:
            # Just write the text exactly as TTS receives it
            lines.append(segment.text)

        output_file.write_text("\n\n".join(lines))
