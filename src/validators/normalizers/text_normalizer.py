"""Abstract base for deterministic text normalizers used by the Validator."""
from abc import ABC, abstractmethod


class TextNormalizer(ABC):
    """One-purpose transform that returns a normalized copy of the input text."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Return text after applying this normalization step."""
