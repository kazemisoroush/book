"""Tests for combiner strategies."""
import pytest
from unittest.mock import Mock, patch
from .simple_concat_strategy import SimpleConcatStrategy
from .crossfade_strategy import CrossfadeStrategy


class TestSimpleConcatStrategy:
    """Tests for SimpleConcatStrategy."""

    @pytest.fixture
    def strategy(self):
        return SimpleConcatStrategy()

    @patch('subprocess.run')
    def test_combine_multiple_files(self, mock_run, strategy, tmp_path):
        # Setup
        mock_run.return_value = Mock(returncode=0, stderr="")

        segment_files = [
            tmp_path / "seg1.wav",
            tmp_path / "seg2.wav",
            tmp_path / "seg3.wav",
        ]

        # Create dummy files
        for f in segment_files:
            f.touch()

        output_file = tmp_path / "output.wav"

        # Execute
        strategy.combine(segment_files, output_file)

        # Verify ffmpeg was called with correct args
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert 'ffmpeg' in call_args
        assert '-f' in call_args
        assert 'concat' in call_args
        assert '-c' in call_args
        assert 'copy' in call_args

    def test_combine_single_file_copies(self, strategy, tmp_path):
        # Setup
        segment_file = tmp_path / "seg1.wav"
        segment_file.write_text("dummy audio data")
        output_file = tmp_path / "output.wav"

        # Execute
        strategy.combine([segment_file], output_file)

        # Verify file was copied
        assert output_file.exists()
        assert output_file.read_text() == "dummy audio data"

    def test_combine_no_files_raises_error(self, strategy, tmp_path):
        output_file = tmp_path / "output.wav"

        with pytest.raises(ValueError, match="No segment files"):
            strategy.combine([], output_file)


class TestCrossfadeStrategy:
    """Tests for CrossfadeStrategy."""

    @pytest.fixture
    def strategy(self):
        return CrossfadeStrategy(crossfade_duration=0.2)

    @patch('subprocess.run')
    def test_combine_uses_crossfade_filter(self, mock_run, strategy, tmp_path):
        # Setup
        mock_run.return_value = Mock(returncode=0, stderr="")

        segment_files = [
            tmp_path / "seg1.wav",
            tmp_path / "seg2.wav",
        ]

        for f in segment_files:
            f.touch()

        output_file = tmp_path / "output.wav"

        # Execute
        strategy.combine(segment_files, output_file)

        # Verify ffmpeg was called with filter_complex
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert '-filter_complex' in call_args

        # Check for acrossfade in the filter
        filter_idx = call_args.index('-filter_complex')
        filter_string = call_args[filter_idx + 1]
        assert 'acrossfade' in filter_string
        assert 'd=0.2' in filter_string

    def test_crossfade_duration_configurable(self):
        strategy = CrossfadeStrategy(crossfade_duration=0.5)
        assert strategy.crossfade_duration == 0.5
