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


def test_identical_text_passes():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="Hello world.", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="narration", text="Hello world.", char_id=1),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is True


def test_case_difference_passes_with_lowercase_normalizer():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="IT is a truth.", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="narration", text="It is a truth.", char_id=1),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is True


def test_punctuation_difference_passes():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="“Hello, world!”", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="dialogue", text="Hello world", char_id=2),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is True


def test_dropped_word_fails():
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
    assert result is False


def test_added_word_fails():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(id=1, text="Hello world.", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="narration", text="Hello cruel world.", char_id=1),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is False


def test_split_section_into_multiple_beats_passes():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = _input([
        PromptInputSection(
            id=1,
            text='“I have no money,” I quietly replied.',
            type="text",
        ),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="dialogue", text="I have no money.", char_id=2),
        PromptOutputBeat(id=2, type="narration", text="I quietly replied.", char_id=1),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is True


def test_skip_types_excludes_announcements():
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
    assert result is True


def test_skip_types_still_catches_drift_in_remaining_text():
    # Arrange
    validator = TextValidator(
        _default_normalizers(),
        skip_types={"book_title_announcement"},
    )
    prompt_input = _input([
        PromptInputSection(
            id=1,
            text="The Gambler, by Dostoyevsky.",
            type="book_title_announcement",
        ),
        PromptInputSection(id=2, text="At length I returned.", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(
            id=1,
            type="book_title_announcement",
            text="The Gambler, by Fyodor Dostoyevsky.",
            char_id=1,
        ),
        PromptOutputBeat(
            id=2, type="narration", text="At length I went back.", char_id=1,
        ),
    ])

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is False


def test_normalizers_applied_in_order():
    # Arrange
    calls: list[str] = []

    class _Recorder(TextNormalizer):
        def __init__(self, tag: str):
            self._tag = tag

        def normalize(self, text: str) -> str:
            calls.append(self._tag)
            return text

    validator = TextValidator([_Recorder("a"), _Recorder("b"), _Recorder("c")])
    prompt_input = _input([
        PromptInputSection(id=1, text="x", type="text"),
    ])
    prompt_output = _output([
        PromptOutputBeat(id=1, type="narration", text="x", char_id=1),
    ])

    # Act
    validator.validate(prompt_input, prompt_output)

    # Assert
    assert calls == ["a", "b", "c", "a", "b", "c"]


def test_multiple_chapters_concatenated():
    # Arrange
    validator = TextValidator(_default_normalizers())
    prompt_input = PromptInput(
        metadata=PromptInputMetadata(title="t", author="a"),
        chapters=[
            PromptInputChapter(
                id=1,
                sections=[PromptInputSection(id=1, text="One.", type="text")],
            ),
            PromptInputChapter(
                id=2,
                sections=[PromptInputSection(id=1, text="Two.", type="text")],
            ),
        ],
    )
    prompt_output = PromptOutput(
        chapters=[
            PromptOutputChapter(
                id=1,
                beats=[PromptOutputBeat(id=1, type="narration", text="One.", char_id=1)],
            ),
            PromptOutputChapter(
                id=2,
                beats=[PromptOutputBeat(id=1, type="narration", text="Two.", char_id=1)],
            ),
        ],
        characters=[],
    )

    # Act
    result = validator.validate(prompt_input, prompt_output)

    # Assert
    assert result is True
