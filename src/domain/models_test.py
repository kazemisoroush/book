"""Tests for domain models."""
from .models import (
    Segment, SegmentType, Section, Chapter, Book, BookMetadata, BookContent,
    EmphasisSpan,
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


# ── EmphasisSpan ──────────────────────────────────────────────────────────────

class TestEmphasisSpan:
    """Tests for EmphasisSpan model."""

    def test_create_emphasis_span_with_all_fields(self) -> None:
        """EmphasisSpan stores start, end, and kind correctly."""
        span = EmphasisSpan(start=4, end=9, kind="em")
        assert span.start == 4
        assert span.end == 9
        assert span.kind == "em"

    def test_emphasis_span_accepts_all_inline_tag_kinds(self) -> None:
        """EmphasisSpan accepts each expected inline tag name."""
        for kind in ("em", "b", "strong", "i"):
            span = EmphasisSpan(start=0, end=5, kind=kind)
            assert span.kind == kind

    def test_emphasis_span_zero_width_is_valid(self) -> None:
        """EmphasisSpan with start == end is structurally valid."""
        span = EmphasisSpan(start=3, end=3, kind="em")
        assert span.start == span.end


# ── Section.emphases ──────────────────────────────────────────────────────────

class TestSectionEmphases:
    """Tests for the emphases field on Section."""

    def test_section_emphases_defaults_to_empty_list(self) -> None:
        """Section created without emphases has an empty list, not None."""
        section = Section(text="Hello world.")
        assert section.emphases == []

    def test_section_emphases_accepts_span_list(self) -> None:
        """Section stores a list of EmphasisSpan objects."""
        span = EmphasisSpan(start=0, end=5, kind="em")
        section = Section(text="Hello world.", emphases=[span])
        assert len(section.emphases) == 1
        assert section.emphases[0].kind == "em"

    def test_section_existing_construction_still_works(self) -> None:
        """Section(text=...) without emphases keyword still works."""
        section = Section(text="Plain text.")
        assert section.text == "Plain text."
        assert section.segments is None
        assert section.emphases == []

    def test_section_emphases_are_independent_across_instances(self) -> None:
        """Two Section instances do not share the same emphases list."""
        s1 = Section(text="A")
        s2 = Section(text="B")
        s1.emphases.append(EmphasisSpan(start=0, end=1, kind="b"))
        assert s2.emphases == []



# ── to_dict serialisation of emphases ─────────────────────────────────────────

class TestToDictWithEmphases:
    """Tests that Book.to_dict() serialises EmphasisSpan correctly."""

    def test_to_dict_serialises_section_emphases(self) -> None:
        """emphases list on Section appears in to_dict output."""
        span = EmphasisSpan(start=0, end=5, kind="em")
        section = Section(text="Hello world.", emphases=[span])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        result = book.to_dict()
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert 'emphases' in section_dict
        assert len(section_dict['emphases']) == 1
        assert section_dict['emphases'][0]['start'] == 0
        assert section_dict['emphases'][0]['end'] == 5
        assert section_dict['emphases'][0]['kind'] == "em"

    def test_to_dict_serialises_empty_emphases_as_empty_list(self) -> None:
        """Section with no emphasis spans serialises as an empty list."""
        section = Section(text="Plain.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        result = book.to_dict()
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict['emphases'] == []

