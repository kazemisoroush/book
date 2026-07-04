"""Metric that fails when a run of input text is dropped from the parsed beats."""
from collections.abc import Iterable
from difflib import SequenceMatcher

from src.domain.models import Book
from src.trimmers.beat_trimmer import BeatTrimmer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.text_comparing_validator import TextComparingValidator
from src.validators.validation_result import ValidationResult

_MIN_DROP_CHARS = 40
_PREVIEW = 80
_MAX_REPORTED = 5


class SectionCoverageValidator(TextComparingValidator):
    """Flags contiguous spans of input text that never reach the parsed beats."""

    def __init__(
        self,
        normalizers: list[TextNormalizer],
        skip_types: Iterable[str] = (),
        trimmers: Iterable[BeatTrimmer] = (),
        min_drop_chars: int = _MIN_DROP_CHARS,
        threshold: float = 0.0,
    ):
        super().__init__(normalizers, skip_types, trimmers, threshold)
        self._min_drop_chars = min_drop_chars

    def validate(
        self, input_book: Book, output_book: Book,
    ) -> ValidationResult:
        source = self._normalize(self._concat_sections(input_book))
        beats = self._normalize(self._concat_beats(output_book))
        if not source:
            return ValidationResult(deviation=0.0)

        drops = self._dropped_spans(source, beats)
        if not drops:
            return ValidationResult(deviation=0.0)

        dropped_chars = sum(len(span) for span in drops)
        preview = "; ".join(f"{span[:_PREVIEW]!r}" for span in drops[:_MAX_REPORTED])
        extra = "" if len(drops) <= _MAX_REPORTED else f" (+{len(drops) - _MAX_REPORTED} more)"
        return ValidationResult(
            deviation=dropped_chars / len(source),
            detail=f"dropped {len(drops)} span(s): {preview}{extra}",
        )

    def _dropped_spans(self, source: str, beats: str) -> list[str]:
        matcher = SequenceMatcher(None, source, beats, autojunk=False)
        spans: list[str] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag not in ("delete", "replace"):
                continue
            net_dropped = (i2 - i1) - (j2 - j1)
            if (i2 - i1) >= self._min_drop_chars and net_dropped >= self._min_drop_chars:
                spans.append(source[i1:i2].strip())
        return spans
