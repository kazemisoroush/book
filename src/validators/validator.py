"""Abstract base for input/output validators run after the chapter_parser eval."""
from abc import ABC, abstractmethod

from src.domain.models import Book
from src.prompts.chapter_parser.input import PromptInput
from src.validators.validation_result import ValidationResult


class Validator(ABC):
    """One check that the parsed Book is consistent with the prompt input."""

    @abstractmethod
    def validate(
        self, prompt_input: PromptInput, book: Book,
    ) -> ValidationResult:
        """Return how far the book deviates from what the input implies."""
