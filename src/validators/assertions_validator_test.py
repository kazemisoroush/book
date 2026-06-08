"""Tests for AssertionsValidator."""
import json
from pathlib import Path

from src.domain.beat import Beat, BeatType
from src.domain.character import Character
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputMetadata,
)
from src.validators.assertions_validator import AssertionsValidator


def _input() -> PromptInput:
    return PromptInput(
        metadata=PromptInputMetadata(title="t", author="a"),
        chapters=[PromptInputChapter(id=1, sections=[])],
    )


def _book(num_beats: int, num_chars: int) -> Book:
    metadata = BookMetadata(
        title="t", author="a", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    beats = [
        Beat(text="x", beat_type=BeatType.NARRATION) for _ in range(num_beats)
    ]
    chapter = Chapter(
        number=1, title="", sections=[Section(text="", beats=beats)],
    )
    registry = CharacterRegistry(characters=[
        Character(character_id=f"c{i}", name=f"c{i}") for i in range(num_chars)
    ])
    return Book(
        metadata=metadata,
        content=BookContent(chapters=[chapter]),
        character_registry=registry,
    )


def test_all_assertions_met_passes_with_zero_deviation():
    # Arrange
    validator = AssertionsValidator({"num_characters": 3, "num_beats": 20})
    book = _book(num_beats=20, num_chars=3)

    # Act
    result = validator.validate(_input(), book)

    # Assert
    assert result.passed
    assert result.deviation == 0.0


def test_aggregate_deviation_is_mean_across_assertions():
    # Arrange
    validator = AssertionsValidator({"num_characters": 3, "num_beats": 10})
    book = _book(num_beats=10, num_chars=1)

    # Act
    result = validator.validate(_input(), book)

    # Assert
    assert not result.passed
    assert result.deviation == (2 / 3) / 2


def test_from_file_loads_assertions_from_json(tmp_path: Path):
    # Arrange
    path = tmp_path / "assertions.json"
    path.write_text(json.dumps({"num_beats": 4}))
    validator = AssertionsValidator.from_file(path)

    # Act
    result = validator.validate(_input(), _book(num_beats=4, num_chars=99))

    # Assert
    assert result.passed
