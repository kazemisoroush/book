"""Strips leading em-dashes and replaces inner em-dashes with commas."""
import re
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer

_EM_DASH = "—"
_LEADING = re.compile(r"^\s*—\s*")
_INNER = re.compile(r"\s*—\s*")


class EmDashTrimmer(BeatTrimmer):
    """Removes leading `—` and replaces remaining `—` with `, `."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [replace(b, text=_clean(b.text)) for b in beats]


def _clean(text: str) -> str:
    without_leading = _LEADING.sub("", text)
    if _EM_DASH not in without_leading:
        return without_leading
    return _INNER.sub(", ", without_leading)
