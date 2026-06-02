"""Replaces trailing `,` or `;` with `.` on each beat text."""
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer

_TRAILING_TO_REPLACE = (",", ";")


class SentenceEndingNormalizer(BeatTrimmer):
    """Normalises each beat so its text ends with a sentence-terminator."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [replace(b, text=_normalize(b.text)) for b in beats]


def _normalize(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return text
    if stripped[-1] in _TRAILING_TO_REPLACE:
        return stripped[:-1] + "."
    return stripped
