"""Tests for AssertionsValidator."""
import json
from pathlib import Path

from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputMetadata,
)
from src.prompts.chapter_parser.output import (
    PromptOutput,
    PromptOutputBeat,
    PromptOutputChapter,
    PromptOutputCharacter,
)
from src.validators.assertions_validator import AssertionsValidator


def _input() -> PromptInput:
    return PromptInput(
        metadata=PromptInputMetadata(title="t", author="a"),
        chapters=[PromptInputChapter(id=1, sections=[])],
    )


def _output(num_beats: int, num_chars: int) -> PromptOutput:
    beats = [
        PromptOutputBeat(id=i + 1, type="narration", text="x", char_id=1)
        for i in range(num_beats)
    ]
    chars = [
        PromptOutputCharacter(id=i + 1, name=f"c{i}") for i in range(num_chars)
    ]
    return PromptOutput(
        chapters=[PromptOutputChapter(id=1, beats=beats)],
        characters=chars,
    )


def test_all_assertions_met_passes_with_zero_deviation():
    # Arrange
    validator = AssertionsValidator({"num_characters": 3, "num_beats": 20})
    prompt_output = _output(num_beats=20, num_chars=3)

    # Act
    result = validator.validate(_input(), prompt_output)

    # Assert
    assert result.passed
    assert result.deviation == 0.0


def test_aggregate_deviation_is_mean_across_assertions():
    # Arrange
    validator = AssertionsValidator({"num_characters": 3, "num_beats": 10})
    prompt_output = _output(num_beats=10, num_chars=1)

    # Act
    result = validator.validate(_input(), prompt_output)

    # Assert
    assert not result.passed
    assert result.deviation == (2 / 3) / 2


def test_from_file_loads_assertions_from_json(tmp_path: Path):
    # Arrange
    path = tmp_path / "assertions.json"
    path.write_text(json.dumps({"num_beats": 4}))
    validator = AssertionsValidator.from_file(path)

    # Act
    result = validator.validate(_input(), _output(num_beats=4, num_chars=99))

    # Assert
    assert result.passed
