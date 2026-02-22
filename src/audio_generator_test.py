"""Tests for audio generator."""
import pytest
from unittest.mock import Mock
from .audio_generator import AudioGenerator
from .domain.models import Book, Chapter, Segment, SegmentType
from .voice_assignment import VoiceAssigner


class TestAudioGenerator:
    """Tests for AudioGenerator."""

    @pytest.fixture
    def mock_tts_provider(self):
        provider = Mock()
        provider.get_available_voices.return_value = {
            "narrator": "narrator_id",
            "voice1": "voice1_id"
        }
        return provider

    @pytest.fixture
    def voice_assigner(self):
        assigner = VoiceAssigner(narrator_voice="narrator_id")
        assigner.set_available_voices(["voice1_id", "voice2_id"])
        return assigner

    @pytest.fixture
    def generator(self, mock_tts_provider, voice_assigner):
        # Disable combining and announcements for basic unit tests (no ffmpeg needed)
        return AudioGenerator(mock_tts_provider, voice_assigner,
                              use_grouping=False, combine_to_single_file=False,
                              announce_chapters=False)

    @pytest.fixture
    def sample_book(self):
        segments = [
            Segment("Once upon a time", SegmentType.NARRATION),
            Segment("Hello", SegmentType.DIALOGUE, speaker="Alice"),
            Segment("The end", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)
        return Book(title="Test Book", author="Author", chapters=[chapter])

    def test_generate_chapter(self, generator, mock_tts_provider, tmp_path):
        segments = [
            Segment("Narration text", SegmentType.NARRATION),
            Segment("Dialogue text", SegmentType.DIALOGUE, speaker="Alice")
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        generator.generate_chapter(chapter, tmp_path)

        # Should have called synthesize twice
        assert mock_tts_provider.synthesize.call_count == 2

        # Check first call (narration)
        first_call = mock_tts_provider.synthesize.call_args_list[0]
        assert first_call[0][0] == "Narration text"
        assert first_call[0][1] == "narrator_id"

        # Check second call (dialogue)
        second_call = mock_tts_provider.synthesize.call_args_list[1]
        assert second_call[0][0] == "Dialogue text"
        # Alice should get voice1_id (first in pool)
        assert second_call[0][1] == "voice1_id"

    def test_generate_audiobook(self, generator, mock_tts_provider, sample_book, tmp_path):
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        generator.generate_audiobook(sample_book, tmp_path, progress_callback)

        # Should have created chapter directory with pattern: 000_chapter_001
        chapter_dir = tmp_path / "000_chapter_001"
        assert chapter_dir.exists()

        # Should have called synthesize for each segment
        assert mock_tts_provider.synthesize.call_count == 3

        # Should have called progress callback
        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)

    def test_generate_segment_preview(self, generator, mock_tts_provider, tmp_path):
        output_path = tmp_path / "preview.wav"

        generator.generate_segment_preview("Test text", "Alice", output_path)

        mock_tts_provider.synthesize.assert_called_once()
        args = mock_tts_provider.synthesize.call_args[0]
        assert args[0] == "Test text"
        assert args[2] == output_path

    def test_generate_chapter_with_announcement_enabled(self, mock_tts_provider, voice_assigner, tmp_path):
        generator = AudioGenerator(
            mock_tts_provider, voice_assigner,
            use_grouping=False,
            combine_to_single_file=False,
            announce_chapters=True
        )

        segments = [
            Segment("Content text", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        generator.generate_chapter(chapter, tmp_path)

        # Should have called synthesize twice: once for announcement, once for content
        assert mock_tts_provider.synthesize.call_count == 2

        # First call should be the chapter announcement
        first_call = mock_tts_provider.synthesize.call_args_list[0]
        assert first_call[0][0] == "Chapter I"

        # Second call should be the content
        second_call = mock_tts_provider.synthesize.call_args_list[1]
        assert second_call[0][0] == "Content text"

    def test_generate_chapter_with_announcement_disabled(self, mock_tts_provider, voice_assigner, tmp_path):
        generator = AudioGenerator(
            mock_tts_provider, voice_assigner,
            use_grouping=False,
            combine_to_single_file=False,
            announce_chapters=False
        )

        segments = [
            Segment("Content text", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        generator.generate_chapter(chapter, tmp_path)

        # Should have called synthesize only once for content (no announcement)
        assert mock_tts_provider.synthesize.call_count == 1
        first_call = mock_tts_provider.synthesize.call_args_list[0]
        assert first_call[0][0] == "Content text"

    def test_generate_with_transcripts_enabled(self, mock_tts_provider, voice_assigner, tmp_path):
        generator = AudioGenerator(
            mock_tts_provider, voice_assigner,
            use_grouping=False,
            combine_to_single_file=False,  # Disable combining to avoid file issues in tests
            write_transcripts=True,
            announce_chapters=False
        )

        segments = [
            Segment("Content text", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        generator.generate_chapter(chapter, tmp_path / "001_chapter_001")

        # Should have created transcript file alongside audio
        transcript_file = tmp_path / "001_chapter_001.txt"
        assert transcript_file.exists()
        content = transcript_file.read_text()
        # Should contain text with speaker annotations
        assert "Content text" in content
        assert "[NARRATION]" in content

    def test_generate_with_transcripts_disabled(self, mock_tts_provider, voice_assigner, tmp_path):
        generator = AudioGenerator(
            mock_tts_provider, voice_assigner,
            use_grouping=False,
            combine_to_single_file=False,  # Disable combining to avoid file issues in tests
            write_transcripts=False,
            announce_chapters=False
        )

        segments = [
            Segment("Content text", SegmentType.NARRATION)
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        generator.generate_chapter(chapter, tmp_path / "001_chapter_001")

        # Should NOT have created transcript file
        transcript_file = tmp_path / "001_chapter_001.txt"
        assert not transcript_file.exists()
