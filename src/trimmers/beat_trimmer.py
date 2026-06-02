"""Abstract base for deterministic post-LLM beat trimmers."""
from abc import ABC, abstractmethod

from src.prompts.chapter_parser.output import PromptOutputBeat


class BeatTrimmer(ABC):
    """One-purpose transform over a list of beats returned by the chapter_parser prompt."""

    @abstractmethod
    def trim(self, beats: list[PromptOutputBeat]) -> list[PromptOutputBeat]:
        """Return a new list of beats after applying this trimmer."""
