"""Moves sentence punctuation from inside a closing quote to outside."""
import re
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer

_PATTERN = re.compile(r"([,;.?!])([\"”’'])")


class QuotedPunctuationTrimmer(BeatTrimmer):
    """Normalises punctuation so `,`, `;`, `.`, `?`, `!` never sit inside a closing quote."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [replace(b, text=_PATTERN.sub(r'\2\1', b.text)) for b in beats]
