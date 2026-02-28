"""Tests for domain models."""
from .models import Segment, SegmentType, Section, Chapter, Book


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


class TestSection:
    """Tests for Section model."""

    def test_create_section_without_segments(self):
        """Test section with just text (plain narration paragraph)."""
        section = Section(text="It was a beautiful day. The sun shone brightly.")

        assert section.text == "It was a beautiful day. The sun shone brightly."
        assert section.segments is None

    def test_create_section_with_segments(self):
        """Test section with dialogue breakdown into segments."""
        segment1 = Segment(
            text="Hello there,",
            segment_type=SegmentType.DIALOGUE,
            speaker="John"
        )
        segment2 = Segment(
            text="said John.",
            segment_type=SegmentType.NARRATION
        )

        section = Section(
            text='"Hello there," said John.',
            segments=[segment1, segment2]
        )

        assert section.text == '"Hello there," said John.'
        assert section.segments is not None
        assert len(section.segments) == 2
        assert section.segments[0].is_dialogue()
        assert section.segments[1].is_narration()


class TestChapter:
    """Tests for Chapter model."""

    def test_create_chapter(self):
        """Test chapter contains sections (paragraphs)."""
        section1 = Section(text="It was a dark night.")
        section2 = Section(text="The wind howled.")

        chapter = Chapter(
            number=1,
            title="Chapter I",
            sections=[section1, section2]
        )

        assert chapter.number == 1
        assert chapter.title == "Chapter I"
        assert len(chapter.sections) == 2


class TestBook:
    """Tests for Book model."""

    def test_create_book(self):
        section = Section(text="Once upon a time.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        book = Book(title="Test Book", author="Test Author", chapters=[chapter])

        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert len(book.chapters) == 1
