"""Tests for segment grouper."""
import pytest
from .segment_grouper import SegmentGrouper
from .domain.models import Segment, SegmentType


class TestSegmentGrouper:
    """Tests for SegmentGrouper."""

    @pytest.fixture
    def grouper(self):
        return SegmentGrouper()

    def test_merge_consecutive_dialogue_same_speaker(self, grouper):
        segments = [
            Segment("Hello there,", SegmentType.DIALOGUE, speaker="John"),
            Segment("how are you?", SegmentType.DIALOGUE, speaker="John"),
        ]

        grouped = grouper.group_segments(segments)

        assert len(grouped) == 1
        assert grouped[0].text == "Hello there, how are you?"
        assert grouped[0].speaker == "John"

    def test_dont_merge_different_speakers(self, grouper):
        segments = [
            Segment("Hello", SegmentType.DIALOGUE, speaker="John"),
            Segment("Hi there", SegmentType.DIALOGUE, speaker="Jane"),
        ]

        grouped = grouper.group_segments(segments)

        assert len(grouped) == 2
        assert grouped[0].speaker == "John"
        assert grouped[1].speaker == "Jane"

    def test_merge_short_narration_fragments(self, grouper):
        segments = [
            Segment("He walked in.", SegmentType.NARRATION),
            Segment("said John.", SegmentType.NARRATION),
            Segment("She smiled.", SegmentType.NARRATION),
        ]

        grouped = grouper.group_segments(segments)

        # Should merge the short "said John" with surrounding narration
        assert len(grouped) <= 2

    def test_filter_attribution_only_fragments(self, grouper):
        segments = [
            Segment("Hello", SegmentType.DIALOGUE, speaker="John"),
            Segment("said John", SegmentType.NARRATION),
            Segment("She nodded.", SegmentType.NARRATION),
        ]

        grouped = grouper.group_segments(segments)

        # "said John" should be merged with following narration
        # since it's a short fragment
        assert len(grouped) == 2
        assert grouped[0].is_dialogue()
        assert grouped[0].text == "Hello"
        # Narration segments should be combined
        assert grouped[1].is_narration()

    def test_keep_substantial_narration(self, grouper):
        segments = [
            Segment("It was a dark and stormy night.", SegmentType.NARRATION),
            Segment("Hello", SegmentType.DIALOGUE, speaker="John"),
        ]

        grouped = grouper.group_segments(segments)

        assert len(grouped) == 2
        assert grouped[0].text == "It was a dark and stormy night."

    def test_merge_narration_with_continuation(self, grouper):
        segments = [
            Segment("He walked in", SegmentType.NARRATION),
            Segment("slowly and carefully.", SegmentType.NARRATION),
        ]

        grouped = grouper.group_segments(segments)

        assert len(grouped) == 1
        assert "slowly and carefully" in grouped[0].text
