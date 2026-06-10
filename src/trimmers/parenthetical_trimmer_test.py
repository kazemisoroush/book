"""Tests for ParentheticalTrimmer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.parenthetical_trimmer import ParentheticalTrimmer


def _beat(text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=1, type="narration", text=text, char_id=1)


def test_whole_beat_parenthetical_aside_unwrapped():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("(For, you see, Alice had learnt several things of this sort.)")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "For, you see, Alice had learnt several things of this sort."


def test_leading_parenthetical_followed_by_more_sentence_stripped():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat(
        "(When she thought it over afterwards, it occurred to her that she ought to "
        "have wondered at this); but when the Rabbit actually took a watch out.",
    )]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == (
        "When she thought it over afterwards, it occurred to her that she ought to "
        "have wondered at this; but when the Rabbit actually took a watch out."
    )


def test_inner_parens_in_larger_sentence_stripped():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("she said (sort of) yes")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "she said sort of yes"


def test_multiple_parenthetical_groups_all_stripped():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("(one) middle (two) end (three)")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "one middle two end three"


def test_unbalanced_open_paren_stripped():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("(unbalanced text")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "unbalanced text"


def test_unbalanced_close_paren_stripped():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("unbalanced text)")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "unbalanced text"


def test_text_without_parens_unchanged():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("plain text with no parens")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "plain text with no parens"


def test_empty_list_returns_empty_list():
    # Arrange
    trimmer = ParentheticalTrimmer()

    # Act
    result = trimmer.trim([])

    # Assert
    assert result == []


def test_empty_text_unchanged():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == ""


def test_other_beat_fields_are_preserved():
    # Arrange
    trimmer = ParentheticalTrimmer()
    original = PromptOutputBeat(
        id=9, type="narration", text="(an aside)", char_id=2,
        sec_id=4, emotion="warm",
    )

    # Act
    result = trimmer.trim([original])

    # Assert
    assert result[0].text == "an aside"
    assert result[0].id == 9
    assert result[0].type == "narration"
    assert result[0].char_id == 2
    assert result[0].sec_id == 4
    assert result[0].emotion == "warm"
