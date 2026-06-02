"""Tests for SentenceEndingNormalizer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.sentence_ending_normalizer import SentenceEndingNormalizer


def _beat(text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=1, type="narration", text=text, character_id=1)


def test_trailing_comma_becomes_period():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("Thought Alice,")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == "Thought Alice."


def test_trailing_semicolon_becomes_period():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("Said Alice;")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == "Said Alice."


def test_trailing_period_is_preserved():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("Hello world.")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == "Hello world."


def test_trailing_question_mark_is_preserved():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("Where am I?")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == "Where am I?"


def test_trailing_exclamation_is_preserved():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("Watch out!")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == "Watch out!"


def test_trailing_whitespace_before_punctuation_is_handled():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("Said Alice,   ")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == "Said Alice."


def test_other_beat_fields_are_preserved():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    original = PromptOutputBeat(
        id=7, type="dialogue", text="Hello,", character_id=3, emotion="warm",
    )

    # Act
    result = normalizer.trim([original])

    # Assert
    assert result[0].id == 7
    assert result[0].type == "dialogue"
    assert result[0].character_id == 3
    assert result[0].emotion == "warm"


def test_empty_list_returns_empty_list():
    # Arrange
    normalizer = SentenceEndingNormalizer()

    # Act
    result = normalizer.trim([])

    # Assert
    assert result == []


def test_empty_text_is_left_alone():
    # Arrange
    normalizer = SentenceEndingNormalizer()
    beats = [_beat("")]

    # Act
    result = normalizer.trim(beats)

    # Assert
    assert result[0].text == ""
