"""Abstract base for input/output validators run after the chapter_parser eval."""
from abc import ABC, abstractmethod

from src.prompts.chapter_parser.input import PromptInput
from src.prompts.chapter_parser.output import PromptOutput
from src.validators.validation_result import ValidationResult


class Validator(ABC):
    """One check that the prompt output is consistent with the prompt input."""

    @abstractmethod
    def validate(
        self, prompt_input: PromptInput, prompt_output: PromptOutput,
    ) -> ValidationResult:
        """Return how far the output deviates from what the input implies."""
