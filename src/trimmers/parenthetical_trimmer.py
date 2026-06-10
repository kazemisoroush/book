"""Removes wrapping parentheses from beats that are a single parenthetical aside."""
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer


class ParentheticalTrimmer(BeatTrimmer):
    """Strips a leading `(` and trailing `)` when the beat text is wrapped in them."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [replace(b, text=_unwrap(b.text)) for b in beats]


def _unwrap(text: str) -> str:
    stripped = text.strip()
    if len(stripped) < 2 or stripped[0] != "(" or stripped[-1] != ")":
        return text
    return stripped[1:-1]
