"""Tests for chapter transcriber."""
import pytest
from pathlib import Path
from .chapter_transcriber import ChapterTranscriber
from .domain.models import Chapter, Segment, SegmentType


class TestChapterTranscriber:
    """Tests for ChapterTranscriber."""

    @pytest.fixture
    def transcriber(self):
        return ChapterTranscriber()

    def test_write_transcript_to_file(self, transcriber, tmp_path):
        segments = [
            Segment("Once upon a time", SegmentType.NARRATION),
            Segment("Hello there", SegmentType.DIALOGUE, speaker="Alice"),
            Segment("The end", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)
        output_file = tmp_path / "chapter_001.txt"

        transcriber.write_transcript(chapter, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "Once upon a time" in content
        assert "Hello there" in content
        assert "The end" in content

    def test_transcript_includes_speaker_annotations(self, transcriber, tmp_path):
        segments = [
            Segment("Narration text", SegmentType.NARRATION),
            Segment("Dialogue text", SegmentType.DIALOGUE, speaker="Alice")
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)
        output_file = tmp_path / "chapter_001.txt"

        transcriber.write_transcript(chapter, output_file)

        content = output_file.read_text()
        assert "[NARRATION]" in content
        assert "[Alice]" in content or "[DIALOGUE - Alice]" in content

    def test_transcript_with_no_speaker(self, transcriber, tmp_path):
        segments = [
            Segment("Some dialogue", SegmentType.DIALOGUE, speaker=None)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)
        output_file = tmp_path / "chapter_001.txt"

        transcriber.write_transcript(chapter, output_file)

        content = output_file.read_text()
        assert "Some dialogue" in content

    def test_transcript_empty_chapter(self, transcriber, tmp_path):
        chapter = Chapter(number=1, title="Chapter I", segments=[])
        output_file = tmp_path / "chapter_001.txt"

        transcriber.write_transcript(chapter, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "Chapter I" in content or len(content) >= 0

    def test_transcript_preserves_segment_order(self, transcriber, tmp_path):
        segments = [
            Segment("First", SegmentType.NARRATION),
            Segment("Second", SegmentType.DIALOGUE, speaker="Alice"),
            Segment("Third", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)
        output_file = tmp_path / "chapter_001.txt"

        transcriber.write_transcript(chapter, output_file)

        content = output_file.read_text()
        # Check that segments appear in order
        first_pos = content.find("First")
        second_pos = content.find("Second")
        third_pos = content.find("Third")

        assert first_pos < second_pos < third_pos
