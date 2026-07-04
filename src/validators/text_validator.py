"""Deterministic text-equivalence check between the input and output Books."""
from difflib import SequenceMatcher

from src.domain.models import Book
from src.validators.text_comparing_validator import TextComparingValidator
from src.validators.validation_result import ValidationResult


class TextValidator(TextComparingValidator):
    """Scores how far the parsed beat text drifts from the input section text."""

    def validate(
        self, input_book: Book, output_book: Book,
    ) -> ValidationResult:
        normalized_input = self._normalize(self._concat_sections(input_book))
        normalized_output = self._normalize(self._concat_beats(output_book))
        ratio = SequenceMatcher(None, normalized_input, normalized_output).ratio()
        return ValidationResult(deviation=1.0 - ratio)
