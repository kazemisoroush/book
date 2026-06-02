"""Tests for CapitalizationFixer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.capitalization_fixer import CapitalizationFixer


def _beat(text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=1, type="narration", text=text, character_id=1)


def test_lowercase_first_letter_is_capitalized():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("alice was beginning to get tired.")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == "Alice was beginning to get tired."


def test_already_capitalized_text_is_unchanged():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("Alice was beginning to get tired.")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == "Alice was beginning to get tired."


def test_only_first_letter_is_changed():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("alice WAS very tired.")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == "Alice WAS very tired."


def test_leading_whitespace_is_skipped():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("  alice was here.")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == "  Alice was here."


def test_leading_punctuation_is_skipped():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("\"alice spoke softly.\"")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == "\"Alice spoke softly.\""


def test_empty_text_is_left_alone():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == ""


def test_text_with_no_letters_is_left_alone():
    # Arrange
    fixer = CapitalizationFixer()
    beats = [_beat("123!")]

    # Act
    result = fixer.trim(beats)

    # Assert
    assert result[0].text == "123!"


def test_other_beat_fields_are_preserved():
    # Arrange
    fixer = CapitalizationFixer()
    original = PromptOutputBeat(
        id=4, type="dialogue", text="hello.", character_id=2, emotion="sleepy",
    )

    # Act
    result = fixer.trim([original])

    # Assert
    assert result[0].id == 4
    assert result[0].type == "dialogue"
    assert result[0].character_id == 2
    assert result[0].emotion == "sleepy"
