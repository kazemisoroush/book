"""Shared base for metrics that compare normalized input sections and output beats."""
from collections.abc import Iterable

from src.domain.models import Book
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator


class TextComparingValidator(Validator):
    """Base that normalizes and trims input sections and output beats the same way."""

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

    def _result(self, deviation: float, detail: str = "") -> ValidationResult:
        """Build a result stamped with this metric's own pass threshold."""
        return ValidationResult(
            deviation=deviation, threshold=self._threshold, detail=detail,
        )

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
        return self._join_trimmed(wrapped)

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
        return self._join_trimmed(wrapped)

    def _join_trimmed(self, beats: list[PromptOutputBeat]) -> str:
        for trimmer in self._trimmers:
            beats = trimmer.trim(beats)
        return " ".join(beat.text for beat in beats)

    def _normalize(self, text: str) -> str:
        for normalizer in self._normalizers:
            text = normalizer.normalize(text)
        return text
