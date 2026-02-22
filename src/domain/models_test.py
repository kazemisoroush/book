"""Tests for domain models."""
from .models import Segment, SegmentType, Chapter, Book


class TestSegment:
    """Tests for Segment model."""

    def test_create_narration_segment(self):
        segment = Segment(
            text="It was a dark and stormy night.",
            segment_type=SegmentType.NARRATION
        )

        assert segment.text == "It was a dark and stormy night."
        assert segment.is_narration()
        assert not segment.is_dialogue()
        assert segment.speaker is None

    def test_create_dialogue_segment(self):
        segment = Segment(
            text="Hello, how are you?",
            segment_type=SegmentType.DIALOGUE,
            speaker="John"
        )

        assert segment.text == "Hello, how are you?"
        assert segment.is_dialogue()
        assert not segment.is_narration()
        assert segment.speaker == "John"


class TestChapter:
    """Tests for Chapter model."""

    def test_create_chapter(self):
        segments = [
            Segment("Once upon a time", SegmentType.NARRATION),
            Segment("Hello!", SegmentType.DIALOGUE, speaker="Hero")
        ]

        chapter = Chapter(number=1, title="Chapter I", segments=segments)

        assert chapter.number == 1
        assert chapter.title == "Chapter I"
        assert len(chapter.segments) == 2


class TestBook:
    """Tests for Book model."""

    def test_create_book(self):
        chapter = Chapter(number=1, title="Chapter I", segments=[])
        book = Book(title="Test Book", author="Test Author", chapters=[chapter])

        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert len(book.chapters) == 1
