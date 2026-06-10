"""Strips every `(` and `)` since parentheses are not audible in TTS."""
import re
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer

_PARENS = re.compile(r"[()]")
_MULTI_SPACE = re.compile(r" {2,}")


class ParentheticalTrimmer(BeatTrimmer):
    """Removes every parenthesis character from each beat text."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [replace(b, text=_strip_parens(b.text)) for b in beats]


def _strip_parens(text: str) -> str:
    if "(" not in text and ")" not in text:
        return text
    return _MULTI_SPACE.sub(" ", _PARENS.sub("", text)).strip()
