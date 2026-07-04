"""Checks the parsed Book against a sidecar dict of count assertions."""
import json
from pathlib import Path
from typing import Callable

from src.domain.models import Book
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator

_AssertionFn = Callable[[Book], int]

_ASSERTIONS: dict[str, _AssertionFn] = {
    "num_characters": lambda b: len(b.character_registry.characters),
    "num_beats": lambda b: sum(len(c.beats) for c in b.content.chapters),
    "num_chapters": lambda b: len(b.content.chapters),
    "num_characters_missing_gender": lambda b: sum(
        1 for c in b.character_registry.characters if not c.gender
    ),
    "num_characters_missing_age": lambda b: sum(
        1 for c in b.character_registry.characters if not c.age
    ),
    "num_characters_missing_accent": lambda b: sum(
        1 for c in b.character_registry.characters if not c.accent
    ),
}


class AssertionsValidator(Validator):
    """Scores the parsed Book against integer count assertions."""

    def __init__(self, assertions: dict[str, int], threshold: float = 0.0):
        super().__init__(threshold)
        self._assertions = dict(assertions)

    @classmethod
    def from_file(cls, path: Path) -> "AssertionsValidator":
        return cls(json.loads(path.read_text()))

    def validate(
        self, input_book: Book, output_book: Book,
    ) -> ValidationResult:
        deviations = [
            _count_deviation(expected, _ASSERTIONS[key](output_book))
            for key, expected in self._assertions.items()
            if key in _ASSERTIONS
        ]
        if not deviations:
            return ValidationResult(deviation=0.0)
        return ValidationResult(deviation=sum(deviations) / len(deviations))


def _count_deviation(expected: int, actual: int) -> float:
    if expected == actual:
        return 0.0
    return abs(actual - expected) / max(actual, expected, 1)
