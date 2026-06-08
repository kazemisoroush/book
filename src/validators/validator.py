"""Abstract base for validators run after the chapter_parser eval."""
from abc import ABC, abstractmethod

from src.domain.models import Book
from src.validators.validation_result import ValidationResult


class Validator(ABC):
    """One check that the output Book is consistent with the input Book."""

    @abstractmethod
    def validate(
        self, input_book: Book, output_book: Book,
    ) -> ValidationResult:
        """Return how far the output deviates from what the input implies."""
