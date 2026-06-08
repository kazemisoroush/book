"""Tests for TextValidator."""
from src.domain.beat import Beat, BeatType
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.validators.normalizers.lowercase_normalizer import LowercaseNormalizer
from src.validators.normalizers.punctuation_normalizer import PunctuationNormalizer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.normalizers.whitespace_normalizer import WhitespaceNormalizer
from src.validators.text_validator import TextValidator


def _book_with_sections(sections: list[Section]) -> Book:
    metadata = BookMetadata(
        title="t", author="a", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=1, title="", sections=sections)
    return Book(metadata=metadata, content=BookContent(chapters=[chapter]))


def _book_with_beats(beats: list[Beat]) -> Book:
    return _book_with_sections([Section(text="", beats=beats)])


def _default_normalizers() -> list[TextNormalizer]:
    return [PunctuationNormalizer(), WhitespaceNormalizer(), LowercaseNormalizer()]


def test_normalized_match_passes_with_zero_deviation():
    # Arrange
    validator = TextValidator(_default_normalizers())
    input_book = _book_with_sections([
        Section(text="“IT is a truth.”", section_type="text"),
    ])
    output_book = _book_with_beats([
        Beat(text="It is a truth.", beat_type=BeatType.DIALOGUE),
    ])

    # Act
    result = validator.validate(input_book, output_book)

    # Assert
    assert result.passed
    assert result.deviation == 0.0


def test_dropped_word_drives_deviation_above_zero():
    # Arrange
    validator = TextValidator(_default_normalizers())
    input_book = _book_with_sections([
        Section(text="Hello cruel world.", section_type="text"),
    ])
    output_book = _book_with_beats([
        Beat(text="Hello world.", beat_type=BeatType.NARRATION),
    ])

    # Act
    result = validator.validate(input_book, output_book)

    # Assert
    assert not result.passed
    assert 0.0 < result.deviation <= 1.0


def test_skip_types_excludes_announcement_sections_and_beats():
    # Arrange
    validator = TextValidator(
        _default_normalizers(),
        skip_types={"book_title_announcement", "chapter_announcement"},
    )
    input_book = _book_with_sections([
        Section(
            text="The Gambler, by Dostoyevsky, Fyodor, 1821-1881.",
            section_type="book_title_announcement",
        ),
        Section(text="Chapter 1.", section_type="chapter_announcement"),
        Section(text="At length I returned.", section_type="text"),
    ])
    output_book = _book_with_beats([
        Beat(
            text="The Gambler, by Fyodor Dostoyevsky.",
            beat_type=BeatType.BOOK_TITLE,
        ),
        Beat(text="Chapter One.", beat_type=BeatType.CHAPTER_ANNOUNCEMENT),
        Beat(text="At length I returned.", beat_type=BeatType.NARRATION),
    ])

    # Act
    result = validator.validate(input_book, output_book)

    # Assert
    assert result.passed
