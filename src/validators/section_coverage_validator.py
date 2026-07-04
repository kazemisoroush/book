"""Metric that fails when a run of input text is dropped from the parsed beats."""
from collections.abc import Iterable
from difflib import SequenceMatcher

from src.domain.models import Book
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator

_MIN_DROP_CHARS = 40
_PREVIEW = 80
_MAX_REPORTED = 5


class SectionCoverageValidator(Validator):
    """Flags contiguous spans of input text that never reach the parsed beats."""

    def __init__(
        self,
        normalizers: list[TextNormalizer],
        skip_types: Iterable[str] = (),
        trimmers: Iterable[BeatTrimmer] = (),
        min_drop_chars: int = _MIN_DROP_CHARS,
    ):
        self._normalizers = list(normalizers)
        self._skip_types = frozenset(skip_types)
        self._trimmers = list(trimmers)
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

    def _concat_sections(self, book: Book) -> str:
        wrapped = [
            PromptOutputBeat(
                id=0, type=section.section_type or "narration", text=section.text, char_id=0,
            )
            for chapter in book.content.chapters
            for section in chapter.sections
            if (section.section_type or "") not in self._skip_types
        ]
        return self._join_trimmed(wrapped)

    def _concat_beats(self, book: Book) -> str:
        wrapped = [
            PromptOutputBeat(
                id=0, type=beat.beat_type.value, text=beat.text, char_id=0,
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
