"""Tests for the Validator pass threshold."""
from src.domain.models import Book
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator


class _FixedValidator(Validator):
    """Returns a fixed measurement, for exercising the threshold."""

    def __init__(self, deviation: float, threshold: float = 0.0) -> None:
        super().__init__(threshold)
        self._deviation = deviation

    def validate(self, input_book: Book, output_book: Book) -> ValidationResult:
        return ValidationResult(deviation=self._deviation)


def _passed(deviation: float, threshold: float = 0.0) -> bool:
    validator = _FixedValidator(deviation, threshold)
    return validator.passed(validator.validate(None, None))  # type: ignore[arg-type]


def test_default_threshold_is_strict():
    # Act / Assert
    assert _passed(0.0)
    assert not _passed(0.001)


def test_deviation_within_threshold_passes():
    # Act / Assert
    assert _passed(0.03, threshold=0.05)


def test_deviation_above_threshold_fails():
    # Act / Assert
    assert not _passed(0.06, threshold=0.05)


def test_deviation_equal_to_threshold_passes():
    # Act / Assert
    assert _passed(0.05, threshold=0.05)
