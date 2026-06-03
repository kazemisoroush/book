"""Tests for AudibilityTrimmer."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.audibility_trimmer import AudibilityTrimmer


def _beat(beat_id: int, text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=beat_id, type="narration", text=text, char_id=1)


def test_beat_with_letters_is_kept():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [_beat(1, "Hello world.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert len(result) == 1


def test_scene_marker_is_dropped():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [_beat(1, "* * * * * * * * * *")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result == []


def test_pure_punctuation_is_dropped():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [_beat(1, "...!?,;")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result == []


def test_empty_text_is_dropped():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [_beat(1, "")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result == []


def test_whitespace_only_is_dropped():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [_beat(1, "   \t\n  ")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert result == []


def test_digits_are_audible():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [_beat(1, "1894.")]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert len(result) == 1


def test_mixed_list_drops_only_non_audible():
    # Arrange
    trimmer = AudibilityTrimmer()
    beats = [
        _beat(1, "Hello."),
        _beat(2, "* * * *"),
        _beat(3, "World."),
        _beat(4, ""),
    ]

    # Act
    result = trimmer.trim(beats)

    # Assert
    assert [b.id for b in result] == [1, 3]
