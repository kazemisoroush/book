"""Uppercases the first alphabetic character of each beat text."""
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer


class CapitalizationFixer(BeatTrimmer):
    """Ensures the first alphabetic character of each beat is uppercase."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [replace(b, text=_capitalize_first_letter(b.text)) for b in beats]


def _capitalize_first_letter(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.isalpha():
            if ch.isupper():
                return text
            return text[:i] + ch.upper() + text[i + 1:]
    return text
