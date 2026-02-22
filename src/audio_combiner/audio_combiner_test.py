"""Tests for AudioCombiner."""
from .audio_combiner import AudioCombiner
from .combiner_strategy import CombinerStrategy


class MockStrategy(CombinerStrategy):
    """Mock strategy for testing."""

    def __init__(self):
        self.combine_called = False
        self.combine_args = None

    def combine(self, segment_files, output_file):
        self.combine_called = True
        self.combine_args = (segment_files, output_file)


class TestAudioCombiner:
    """Tests for AudioCombiner."""

    def test_uses_default_strategy(self):
        combiner = AudioCombiner()
        assert combiner.strategy is not None

    def test_accepts_custom_strategy(self):
        strategy = MockStrategy()
        combiner = AudioCombiner(strategy=strategy)
        assert combiner.strategy is strategy

    def test_delegates_to_strategy(self, tmp_path):
        strategy = MockStrategy()
        combiner = AudioCombiner(strategy=strategy)

        segment_files = [tmp_path / "seg1.wav"]
        output_file = tmp_path / "output.wav"

        combiner.combine_segments(segment_files, output_file)

        assert strategy.combine_called
        assert strategy.combine_args == (segment_files, output_file)

    def test_can_change_strategy_at_runtime(self):
        strategy1 = MockStrategy()
        strategy2 = MockStrategy()

        combiner = AudioCombiner(strategy=strategy1)
        assert combiner.strategy is strategy1

        combiner.set_strategy(strategy2)
        assert combiner.strategy is strategy2
