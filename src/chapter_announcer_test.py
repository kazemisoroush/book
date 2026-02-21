"""Tests for chapter announcer."""
import pytest
from .chapter_announcer import ChapterAnnouncer
from .domain.models import Chapter, Segment, SegmentType


class TestChapterAnnouncer:
    """Tests for ChapterAnnouncer."""

    @pytest.fixture
    def announcer(self):
        return ChapterAnnouncer()

    def test_prepend_announcement_to_empty_chapter(self, announcer):
        chapter = Chapter(number=1, title="Chapter I", segments=[])

        result = announcer.add_announcement(chapter)

        assert len(result.segments) == 1
        assert result.segments[0].is_narration()
        assert result.segments[0].text == "Chapter I"
        assert result.segments[0].speaker is None

    def test_prepend_announcement_to_chapter_with_segments(self, announcer):
        segments = [
            Segment("Once upon a time", SegmentType.NARRATION),
            Segment("Hello", SegmentType.DIALOGUE, speaker="Alice")
        ]
        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        result = announcer.add_announcement(chapter)

        assert len(result.segments) == 3
        assert result.segments[0].text == "Chapter I"
        assert result.segments[0].is_narration()
        assert result.segments[1].text == "Once upon a time"
        assert result.segments[2].text == "Hello"

    def test_prepend_announcement_for_preface(self, announcer):
        segments = [Segment("Preface text", SegmentType.NARRATION)]
        chapter = Chapter(number=0, title="Preface", segments=segments)

        result = announcer.add_announcement(chapter)

        assert len(result.segments) == 2
        assert result.segments[0].text == "Preface"
        assert result.segments[1].text == "Preface text"

    def test_prepend_announcement_with_subtitle(self, announcer):
        chapter = Chapter(
            number=2,
            title="Chapter II: The Beginning",
            segments=[Segment("Content", SegmentType.NARRATION)]
        )

        result = announcer.add_announcement(chapter)

        assert result.segments[0].text == "Chapter II: The Beginning"

    def test_does_not_modify_original_chapter(self, announcer):
        original_segments = [Segment("Text", SegmentType.NARRATION)]
        chapter = Chapter(number=1, title="Chapter I", segments=original_segments)

        result = announcer.add_announcement(chapter)

        # Original chapter should be unchanged
        assert len(chapter.segments) == 1
        assert len(result.segments) == 2
        assert result is not chapter
