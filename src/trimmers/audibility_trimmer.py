"""Drops beats whose text has no speakable characters."""
from src.prompts.chapter_parser.output import PromptOutputBeat
from src.trimmers.beat_trimmer import BeatTrimmer


class AudibilityTrimmer(BeatTrimmer):
    """Removes beats whose text contains no letters or digits."""

    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        return [b for b in beats if _is_audible(b.text)]


def _is_audible(text: str) -> bool:
    return any(ch.isalnum() for ch in text)
