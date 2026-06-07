"""Tests for TextValidator."""
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputMetadata,
    PromptInputSection,
)
from src.prompts.chapter_parser.output import (
    PromptOutput,
    PromptOutputBeat,
    PromptOutputChapter,
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


def _output(beats: list[PromptOutputBeat]) -> PromptOutput:
    return PromptOutput(
        chapters=[PromptOutputChapter(id=1, beats=beats)],
        characters=[],
    )


def _default_normalizers() -> list[TextNormalizer]:
    return [PunctuationNormalizer(), WhitespaceNormalizer(), LowercaseNormalizer()]


def test_normalized_match_passes_with_zero_deviation():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="“IT is a truth.”", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="dialogue", text="It is a truth.", char_id=2),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result.passed
    assert result.deviation == 0.0


def test_dropped_word_drives_deviation_above_zero():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="Hello cruel world.", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="narration", text="Hello world.", char_id=1),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert not result.passed
    assert 0.0 < result.deviation <= 1.0


def test_skip_types_excludes_announcement_sections_and_beats():
    # Arrange
    validator = TextValidator(
        _default_normalizers(),
        skip_types={"book_title_announcement", "chapter_announcement"},
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
    prompt_output = _output([
        PromptOutputBeat(
            id=1,
            type="book_title_announcement",
            text="The Gambler, by Fyodor Dostoyevsky.",
            char_id=1,
        ),
        PromptOutputBeat(
            id=2, type="chapter_announcement", text="Chapter One.", char_id=1,
        ),
        PromptOutputBeat(
            id=3, type="narration", text="At length I returned.", char_id=1,
        ),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result.passed
