"""Tests for EmDashTrimmer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.em_dash_trimmer import EmDashTrimmer


def _beat(text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=1, type="dialogue", text=text, char_id=1)


def test_leading_em_dash_stripped():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat("—Yes, hello there.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "Yes, hello there."


def test_leading_em_dash_with_space_stripped():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat("— Yes, hello there.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "Yes, hello there."


def test_inner_em_dash_replaced_with_comma_space():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat("right distance—but then I wonder.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "right distance, but then I wonder."


def test_inner_em_dash_with_spaces_no_double_space():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat("right distance — but then.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "right distance, but then."


def test_leading_and_inner_em_dashes_both_handled():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat(
        "—Yes, that's about the right distance—but then I wonder "
        "what Latitude or Longitude I've got to?",
    )]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == (
        "Yes, that's about the right distance, but then I wonder "
        "what Latitude or Longitude I've got to?"
    )


def test_multiple_inner_em_dashes_all_replaced():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat("one—two—three—four.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "one, two, three, four."


def test_text_without_em_dashes_unchanged():
    # Arrange
    trimmer = EmDashTrimmer()
    beats = [_beat("plain text with no em-dashes.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result[0].text == "plain text with no em-dashes."


def test_empty_list_returns_empty_list():
    # Arrange
    trimmer = EmDashTrimmer()

    # Act
    result = trimmer.trim([])

    # Assert
    assert result == []


def test_other_beat_fields_are_preserved():
    # Arrange
    trimmer = EmDashTrimmer()
    original = PromptOutputBeat(
        id=9, type="dialogue", text="—Yes—maybe.", char_id=2,
        sec_id=4, emotion="thoughtful",
    )

    # Act
    result = trimmer.trim([original])

    # Assert
    assert result[0].text == "Yes, maybe."
    assert result[0].id == 9
    assert result[0].type == "dialogue"
    assert result[0].char_id == 2
    assert result[0].sec_id == 4
    assert result[0].emotion == "thoughtful"
