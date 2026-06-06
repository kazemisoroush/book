"""Removes every Unicode punctuation character from the input text."""
import unicodedata

from src.validators.text_normalizer import TextNormalizer


class PunctuationNormalizer(TextNormalizer):
    """Drops every character whose Unicode category starts with `P`."""

    def normalize(self, text: str) -> str:
        return "".join(
            ch for ch in text if not unicodedata.category(ch).startswith("P")
        )
