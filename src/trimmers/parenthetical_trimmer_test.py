"""Tests for ParentheticalTrimmer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.parenthetical_trimmer import ParentheticalTrimmer


def _beat(text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=1, type="narration", text=text, char_id=1)


def test_wrapping_parens_removed():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("(For, you see, Alice had learnt several things of this sort.)")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "For, you see, Alice had learnt several things of this sort."


def test_wrapping_parens_with_surrounding_whitespace_removed():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("  (a parenthetical aside)  ")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "a parenthetical aside"


def test_inner_parens_in_larger_sentence_unchanged():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("she said (sort of) yes")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "she said (sort of) yes"


def test_only_opening_paren_unchanged():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("(unbalanced text")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "(unbalanced text"


def test_only_closing_paren_unchanged():
    # Arrange
    trimmer = ParentheticalTrimmer()
    beats = [_beat("unbalanced text)")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "unbalanced text)"


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
