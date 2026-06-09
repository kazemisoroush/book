"""Tests for AssertionsValidator."""
import json
from pathlib import Path

from src.domain.beat import Beat, BeatType
from src.domain.character import Character
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, BookContent, BookMetadata, Chapter
from src.validators.assertions_validator import AssertionsValidator


def _empty_input() -> Book:
    metadata = BookMetadata(
        title="t", author="a", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    return Book(metadata=metadata, content=BookContent(chapters=[]))


def _output(num_beats: int, num_chars: int) -> Book:
    metadata = BookMetadata(
        title="t", author="a", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    beats = [
        Beat(text="x", beat_type=BeatType.NARRATION) for _ in range(num_beats)
    ]
    chapter = Chapter(number=1, title="", beats=beats)
    registry = CharacterRegistry(characters=[
        Character(id=i + 1, name=f"c{i}") for i in range(num_chars)
    ])
    return Book(
        metadata=metadata,
        content=BookContent(chapters=[chapter]),
        character_registry=registry,
    )


def test_all_assertions_met_passes_with_zero_deviation():
    # Arrange
    validator = AssertionsValidator({"num_characters": 3, "num_beats": 20})
    output_book = _output(num_beats=20, num_chars=3)

    # Act
    result = validator.validate(_empty_input(), output_book)

    # Assert
    assert result.passed
    assert result.deviation == 0.0


def test_aggregate_deviation_is_mean_across_assertions():
    # Arrange
    validator = AssertionsValidator({"num_characters": 3, "num_beats": 10})
    output_book = _output(num_beats=10, num_chars=1)

    # Act
    result = validator.validate(_empty_input(), output_book)

    # Assert
    assert not result.passed
    assert result.deviation == (2 / 3) / 2


def test_from_file_loads_assertions_from_json(tmp_path: Path):
    # Arrange
    path = tmp_path / "assertions.json"
    path.write_text(json.dumps({"num_beats": 4}))
    validator = AssertionsValidator.from_file(path)

    # Act
    result = validator.validate(_empty_input(), _output(num_beats=4, num_chars=99))

    # Assert
    assert result.passed
