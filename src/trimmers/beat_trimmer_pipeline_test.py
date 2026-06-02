"""Tests for apply_beat_trimmers."""
from src.prompts.chapter_parser.output import (
    PromptOutput,
    PromptOutputBeat,
    PromptOutputChapter,
    PromptOutputCharacter,
)
from src.trimmers.audibility_trimmer import AudibilityTrimmer
from src.trimmers.beat_trimmer_pipeline import apply_beat_trimmers
from src.trimmers.capitalization_trimmer import CapitalizationTrimmer
from src.trimmers.sentence_ending_trimmer import SentenceEndingTrimmer


def _output(beats: list[PromptOutputBeat]) -> PromptOutput:
    return PromptOutput(
        chapters=[PromptOutputChapter(id=1, beats=beats)],
        characters=[PromptOutputCharacter(id=1, name="Narrator")],
    )


def _beat(beat_id: int, text: str) -> PromptOutputBeat:
    return PromptOutputBeat(id=beat_id, type="narration", text=text, character_id=1)


def test_no_trimmers_returns_input_unchanged():
    # Arrange
    output = _output([_beat(1, "Hello.")])

    # Act
    result = apply_beat_trimmers(output, [])

    # Assert
    assert result == output


def test_trimmers_run_in_order():
    # Arrange
    output = _output([_beat(1, "hello,")])
    trimmers = [SentenceEndingTrimmer(), CapitalizationTrimmer()]

    # Act
    result = apply_beat_trimmers(output, trimmers)

    # Assert
    assert result.chapters[0].beats[0].text == "Hello."


def test_dropped_beats_cause_renumber():
    # Arrange
    output = _output([
        _beat(1, "First."),
        _beat(2, "* * * *"),
        _beat(3, "Third."),
    ])

    # Act
    result = apply_beat_trimmers(output, [AudibilityTrimmer()])

    # Assert
    beats = result.chapters[0].beats
    assert [b.id for b in beats] == [1, 2]
    assert [b.text for b in beats] == ["First.", "Third."]


def test_pipeline_applies_to_each_chapter_independently():
    # Arrange
    output = PromptOutput(
        chapters=[
            PromptOutputChapter(id=1, beats=[_beat(1, "* * *"), _beat(2, "Kept.")]),
            PromptOutputChapter(id=2, beats=[_beat(1, "Also kept.")]),
        ],
        characters=[],
    )

    # Act
    result = apply_beat_trimmers(output, [AudibilityTrimmer()])

    # Assert
    assert [b.text for b in result.chapters[0].beats] == ["Kept."]
    assert [b.id for b in result.chapters[0].beats] == [1]
    assert [b.text for b in result.chapters[1].beats] == ["Also kept."]


def test_characters_are_preserved():
    # Arrange
    output = _output([_beat(1, "Hello.")])

    # Act
    result = apply_beat_trimmers(output, [SentenceEndingTrimmer()])

    # Assert
    assert result.characters == output.characters


def test_original_output_is_not_mutated():
    # Arrange
    original_beat = _beat(1, "hello,")
    output = _output([original_beat])

    # Act
    apply_beat_trimmers(output, [SentenceEndingTrimmer(), CapitalizationTrimmer()])

    # Assert
    assert original_beat.text == "hello,"
    assert output.chapters[0].beats[0].text == "hello,"
