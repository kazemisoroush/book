"""Checks the PromptOutput against a sidecar dict of count assertions."""
import json
from pathlib import Path
from typing import Callable

from src.prompts.chapter_parser.input import PromptInput
from src.prompts.chapter_parser.output import PromptOutput
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator

_AssertionFn = Callable[[PromptOutput], int]

_ASSERTIONS: dict[str, _AssertionFn] = {
    "num_characters": lambda o: len(o.characters),
    "num_beats": lambda o: sum(len(ch.beats) for ch in o.chapters),
    "num_chapters": lambda o: len(o.chapters),
}


class AssertionsValidator(Validator):
    """Scores the PromptOutput against integer count assertions."""

    def __init__(self, assertions: dict[str, int]):
        self._assertions = dict(assertions)

    @classmethod
    def from_file(cls, path: Path) -> "AssertionsValidator":
        return cls(json.loads(path.read_text()))

    def validate(
        self, prompt_input: PromptInput, prompt_output: PromptOutput,
    ) -> ValidationResult:
        deviations = [
            _count_deviation(expected, _ASSERTIONS[key](prompt_output))
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
