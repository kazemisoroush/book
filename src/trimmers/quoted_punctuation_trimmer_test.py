"""Tests for QuotedPunctuationTrimmer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.quoted_punctuation_trimmer import QuotedPunctuationTrimmer


def _beat(text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=1, type="narration", text=text, character_id=1)


def test_comma_inside_ascii_quote_moves_outside():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('it was labelled "Orange Marmalade," but empty')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == 'it was labelled "Orange Marmalade", but empty'


def test_semicolon_inside_ascii_quote_moves_outside():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('she said "no;" and walked away')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == 'she said "no"; and walked away'


def test_comma_inside_smart_double_quote_moves_outside():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat("the words “Drink Me,” printed in large letters")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "the words “Drink Me”, printed in large letters"


def test_comma_inside_smart_single_quote_moves_outside():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat("marked ‘poison,’ said Alice")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "marked ‘poison’, said Alice"


def test_dialogue_tag_pattern_also_normalized():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('"Hello," she said.')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == '"Hello", she said.'


def test_multiple_occurrences_all_normalized():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('"yes," "no," "maybe,"')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == '"yes", "no", "maybe",'


def test_quote_without_inner_punctuation_unchanged():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('the sign read "stop" and she stopped')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == 'the sign read "stop" and she stopped'


def test_punctuation_already_outside_unchanged():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('she said "hello", then left')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == 'she said "hello", then left'


def test_period_inside_quote_unchanged():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    beats = [_beat('she said "hello."')]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == 'she said "hello."'


def test_empty_list_returns_empty_list():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()

    # Act
    result = trimmer.trim([])

    # Assert
    assert result == []


def test_other_beat_fields_are_preserved():
    # Arrange
    trimmer = QuotedPunctuationTrimmer()
    original = PromptOutputBeat(
        id=9, type="dialogue", text='"Hello," he said', character_id=2,
        section_id=4, emotion="warm",
    )

    # Act
    result = trimmer.trim([original])

    # Assert
    assert result[0].id == 9
    assert result[0].type == "dialogue"
    assert result[0].character_id == 2
    assert result[0].section_id == 4
    assert result[0].emotion == "warm"
