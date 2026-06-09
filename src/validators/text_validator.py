"""Deterministic text-equivalence check between the input and output Books."""
from collections.abc import Iterable
from difflib import SequenceMatcher

from src.domain.models import Book
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator


class TextValidator(Validator):
    """Scores how far the parsed beat text drifts from the input section text."""

    def __init__(
        self,
        normalizers: list[TextNormalizer],
        skip_types: Iterable[str] = (),
    ):
        self._normalizers = list(normalizers)
        self._skip_types = frozenset(skip_types)

    def validate(
        self, input_book: Book, output_book: Book,
    ) -> ValidationResult:
        normalized_input = self._normalize(self._concat_sections(input_book))
        normalized_output = self._normalize(self._concat_beats(output_book))
        ratio = SequenceMatcher(None, normalized_input, normalized_output).ratio()
        return ValidationResult(deviation=1.0 - ratio)

    def _normalize(self, text: str) -> str:
        for normalizer in self._normalizers:
            text = normalizer.normalize(text)
        return text

    def _concat_sections(self, book: Book) -> str:
        return " ".join(
            section.text
            for chapter in book.content.chapters
            for section in chapter.sections
            if (section.section_type or "") not in self._skip_types
        )

    def _concat_beats(self, book: Book) -> str:
        return " ".join(
            beat.text
            for chapter in book.content.chapters
            for beat in chapter.beats
            if beat.beat_type.value not in self._skip_types
        )
