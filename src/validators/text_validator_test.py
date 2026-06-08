"""Tests for TextValidator."""
from src.domain.beat import Beat, BeatType
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputMetadata,
    PromptInputSection,
)
from src.validators.normalizers.lowercase_normalizer import LowercaseNormalizer
from src.validators.normalizers.punctuation_normalizer import PunctuationNormalizer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.normalizers.whitespace_normalizer import WhitespaceNormalizer
from src.validators.text_validator import TextValidator


def _input(sections: list[PromptInputSection]) -> PromptInput:
    return PromptInput(
        metadata=PromptInputMetadata(title="t", author="a"),
        chapters=[PromptInputChapter(id=1, sections=sections)],
    )


def _book(beats: list[Beat]) -> Book:
    metadata = BookMetadata(
        title="t", author="a", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(
        number=1, title="", sections=[Section(text="", beats=beats)],
    )
    return Book(metadata=metadata, content=BookContent(chapters=[chapter]))


def _default_normalizers() -> list[TextNormalizer]:
    return [PunctuationNormalizer(), WhitespaceNormalizer(), LowercaseNormalizer()]


def test_normalized_match_passes_with_zero_deviation():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="“IT is a truth.”", type="text"),
    ])
    book = _book([
        Beat(text="It is a truth.", beat_type=BeatType.DIALOGUE),
    ])

    # Act
    result = validator.validate(prompt_input, book)

    # Assert
    assert result.passed
    assert result.deviation == 0.0


def test_dropped_word_drives_deviation_above_zero():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="Hello cruel world.", type="text"),
    ])
    book = _book([
        Beat(text="Hello world.", beat_type=BeatType.NARRATION),
    ])

    # Act
    result = validator.validate(prompt_input, book)

    # Assert
    assert not result.passed
    assert 0.0 < result.deviation <= 1.0


def test_skip_types_excludes_announcement_sections_and_beats():
    # Arrange
    validator = TextValidator(
        _default_normalizers(),
        skip_types={
            "book_title_announcement",
            "book_title",
            "chapter_announcement",
        },
    )
    prompt_input = _input([
        PromptInputSection(
            id=1,
            text="The Gambler, by Dostoyevsky, Fyodor, 1821-1881.",
            type="book_title_announcement",
        ),
        PromptInputSection(id=2, text="Chapter 1.", type="chapter_announcement"),
        PromptInputSection(id=3, text="At length I returned.", type="text"),
    ])
    book = _book([
        Beat(
            text="The Gambler, by Fyodor Dostoyevsky.",
            beat_type=BeatType.BOOK_TITLE,
        ),
        Beat(text="Chapter One.", beat_type=BeatType.CHAPTER_ANNOUNCEMENT),
        Beat(text="At length I returned.", beat_type=BeatType.NARRATION),
    ])

    # Act
    result = validator.validate(prompt_input, book)

    # Assert
    assert result.passed
