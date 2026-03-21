"""Tests for domain models."""
from .models import (
    Segment, SegmentType, Section, Chapter, Book, BookMetadata, BookContent
)


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
        section = Section(text="It was a beautiful day.")

        assert section.text == "It was a beautiful day."
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
        metadata = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        assert book.metadata.title == "Test Book"
        assert book.metadata.author == "Test Author"
        assert len(book.content.chapters) == 1

    def test_to_dict_converts_book_to_dictionary(self):
        # Given
        section = Section(text="Once upon a time.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate="2020-01-01",
            language="en",
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # When
        result = book.to_dict()

        # Then
        assert isinstance(result, dict)
        assert result['metadata']['title'] == "Test Book"
        assert result['metadata']['author'] == "Test Author"
        assert result['metadata']['releaseDate'] == "2020-01-01"
        assert len(result['content']['chapters']) == 1
        assert result['content']['chapters'][0]['title'] == "Chapter I"

    def test_to_dict_converts_segment_types_to_strings(self):
        # Given
        segment = Segment(
            text="Hello",
            segment_type=SegmentType.DIALOGUE,
            speaker="John"
        )
        section = Section(text='"Hello"', segments=[segment])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # When
        result = book.to_dict()

        # Then
        segment_dict = result['content']['chapters'][0]['sections'][0]['segments'][0]  # noqa: E501
        assert segment_dict['segment_type'] == "dialogue"
        assert segment_dict['speaker'] == "John"

    def test_to_dict_handles_none_values(self):
        # Given
        section = Section(text="Test")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # When
        result = book.to_dict()

        # Then
        assert result['metadata']['author'] is None
        assert result['metadata']['releaseDate'] is None

    def test_to_dict_handles_sections_without_segments(self):
        # Given
        section = Section(text="Plain narration.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # When
        result = book.to_dict()

        # Then
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict['text'] == "Plain narration."
        assert section_dict['segments'] is None
