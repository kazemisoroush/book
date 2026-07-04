"""Deterministic text-equivalence check between the input and output Books."""
from collections.abc import Iterable
from difflib import SequenceMatcher

from src.domain.models import Book
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator


class TextValidator(Validator):
    """Scores how far the parsed beat text drifts from the input section text."""

    def __init__(
        self,
        normalizers: list[TextNormalizer],
        skip_types: Iterable[str] = (),
        trimmers: Iterable[BeatTrimmer] = (),
        threshold: float = 0.0,
    ):
        self._normalizers = list(normalizers)
        self._skip_types = frozenset(skip_types)
        self._trimmers = list(trimmers)
        self._threshold = threshold

    def validate(
        self, input_book: Book, output_book: Book,
    ) -> ValidationResult:
        normalized_input = self._normalize(self._concat_sections(input_book))
        normalized_output = self._normalize(self._concat_beats(output_book))
        ratio = SequenceMatcher(None, normalized_input, normalized_output).ratio()
        return ValidationResult(deviation=1.0 - ratio, threshold=self._threshold)

    def _normalize(self, text: str) -> str:
        for normalizer in self._normalizers:
            text = normalizer.normalize(text)
        return text

    def _concat_sections(self, book: Book) -> str:
        wrapped = [
            PromptOutputBeat(
                id=0,
                type=section.section_type or "narration",
                text=section.text,
                char_id=0,
            )
            for chapter in book.content.chapters
            for section in chapter.sections
            if (section.section_type or "") not in self._skip_types
        ]
        return " ".join(beat.text for beat in self._apply_trimmers(wrapped))

    def _concat_beats(self, book: Book) -> str:
        wrapped = [
            PromptOutputBeat(
                id=0,
                type=beat.beat_type.value,
                text=beat.text,
                char_id=0,
            )
            for chapter in book.content.chapters
            for beat in chapter.beats
            if beat.beat_type.value not in self._skip_types
        ]
        return " ".join(beat.text for beat in self._apply_trimmers(wrapped))

    def _apply_trimmers(
        self, beats: list[PromptOutputBeat],
    ) -> list[PromptOutputBeat]:
        for trimmer in self._trimmers:
            beats = trimmer.trim(beats)
        return beats
