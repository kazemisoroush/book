"""Main audio generation orchestrator."""
from pathlib import Path
from typing import Optional
from src.domain.models import Book, Chapter
from src.tts.tts_provider import TTSProvider
from src.voice_assignment import VoiceAssigner
from src.segment_grouper import SegmentGrouper
from src.audio_combiner import AudioCombiner, SimpleConcatStrategy


class AudioGenerator:
    """Orchestrates the audio generation process."""

    def __init__(self, tts_provider: TTSProvider, voice_assigner: VoiceAssigner,
                 use_grouping: bool = True, combine_to_single_file: bool = True):
        """
        Initialize audio generator.

        Args:
            tts_provider: TTS provider to use
            voice_assigner: Voice assigner for characters
            use_grouping: Whether to group segments for more natural output
            combine_to_single_file: Whether to combine segments into single chapter file
        """
        self.tts_provider = tts_provider
        self.voice_assigner = voice_assigner
        self.use_grouping = use_grouping
        self.combine_to_single_file = combine_to_single_file
        self.grouper = SegmentGrouper() if use_grouping else None
        self.combiner = AudioCombiner() if combine_to_single_file else None

    def generate_audiobook(self, book: Book, output_dir: Path, progress_callback: Optional[callable] = None) -> None:
        """
        Generate complete audiobook.

        Args:
            book: The book to convert
            output_dir: Directory to save audio files
            progress_callback: Optional callback for progress updates (chapter_num, total_chapters)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        total_chapters = len(book.chapters)

        for chapter in book.chapters:
            chapter_dir = output_dir / f"chapter_{chapter.number:03d}"
            chapter_dir.mkdir(parents=True, exist_ok=True)

            self.generate_chapter(chapter, chapter_dir)

            if progress_callback:
                progress_callback(chapter.number, total_chapters)

    def generate_chapter(self, chapter: Chapter, output_dir: Path) -> Path:
        """
        Generate audio for a single chapter.

        Args:
            chapter: The chapter to convert
            output_dir: Directory to save audio files

        Returns:
            Path to the generated audio file (combined or directory)
        """
        # Group segments if enabled
        segments = chapter.segments
        if self.use_grouping and self.grouper:
            segments = self.grouper.group_segments(segments)

        # Generate individual segment files
        segment_files = []
        segment_num = 0

        for segment in segments:
            # Get the appropriate voice
            voice_id = self.voice_assigner.get_voice_for_character(segment.speaker)

            # Generate filename
            segment_type = "dialogue" if segment.is_dialogue() else "narration"
            speaker_suffix = f"_{segment.speaker}" if segment.speaker else ""
            filename = f"{segment_num:04d}_{segment_type}{speaker_suffix}.wav"
            output_path = output_dir / filename

            # Synthesize
            self.tts_provider.synthesize(segment.text, voice_id, output_path)

            segment_files.append(output_path)
            segment_num += 1

        # Combine into single file if enabled
        if self.combine_to_single_file and self.combiner and segment_files:
            combined_file = output_dir.parent / f"{output_dir.name}.wav"
            self.combiner.combine_segments(segment_files, combined_file)

            # Clean up individual segment files
            for seg_file in segment_files:
                seg_file.unlink(missing_ok=True)

            # Remove the now-empty chapter directory
            output_dir.rmdir()

            return combined_file

        return output_dir

    def generate_chapter_segments_only(self, chapter: Chapter, output_dir: Path) -> list[Path]:
        """
        Generate audio segments without combining.

        Useful for debugging or custom post-processing.

        Args:
            chapter: The chapter to convert
            output_dir: Directory to save audio files

        Returns:
            List of paths to generated segment files
        """
        # Temporarily disable combining
        old_combine = self.combine_to_single_file
        self.combine_to_single_file = False

        try:
            self.generate_chapter(chapter, output_dir)
            return sorted(output_dir.glob("*.wav"))
        finally:
            self.combine_to_single_file = old_combine

    def generate_segment_preview(self, text: str, speaker: Optional[str], output_path: Path) -> None:
        """
        Generate a preview of a single segment.

        Useful for testing voice assignments.

        Args:
            text: Text to synthesize
            speaker: Speaker name (None for narrator)
            output_path: Where to save the preview
        """
        voice_id = self.voice_assigner.get_voice_for_character(speaker)
        self.tts_provider.synthesize(text, voice_id, output_path)
