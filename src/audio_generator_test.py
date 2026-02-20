"""Tests for audio generator."""
import pytest
from pathlib import Path
from unittest.mock import Mock, call
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
        # Disable combining for unit tests (no ffmpeg needed)
        return AudioGenerator(mock_tts_provider, voice_assigner,
                            use_grouping=False, combine_to_single_file=False)

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

        # Should have created chapter directory
        chapter_dir = tmp_path / "chapter_001"
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
