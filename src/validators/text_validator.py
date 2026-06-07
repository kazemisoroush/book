"""Deterministic text-equivalence check between a PromptInput and a PromptOutput."""
from collections.abc import Iterable
from difflib import SequenceMatcher

from src.prompts.chapter_parser.input import PromptInput
from src.prompts.chapter_parser.output import PromptOutput
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator


class TextValidator(Validator):
    """Scores how far the PromptOutput text drifts from the PromptInput text."""

    def __init__(
        self,
        normalizers: list[TextNormalizer],
        skip_types: Iterable[str] = (),
    ):
        self._normalizers = list(normalizers)
        self._skip_types = frozenset(skip_types)

    def validate(
        self, prompt_input: PromptInput, prompt_output: PromptOutput,
    ) -> ValidationResult:
        normalized_input = self._normalize(self._concat_input(prompt_input))
        normalized_output = self._normalize(self._concat_output(prompt_output))
        ratio = SequenceMatcher(None, normalized_input, normalized_output).ratio()
        return ValidationResult(deviation=1.0 - ratio)

    def _normalize(self, text: str) -> str:
        for normalizer in self._normalizers:
            text = normalizer.normalize(text)
        return text

    def _concat_input(self, prompt_input: PromptInput) -> str:
        return " ".join(
            section.text
            for chapter in prompt_input.chapters
            for section in chapter.sections
            if section.type not in self._skip_types
        )

    def _concat_output(self, prompt_output: PromptOutput) -> str:
        return " ".join(
            beat.text
            for chapter in prompt_output.chapters
            for beat in chapter.beats
            if beat.type not in self._skip_types
        )
