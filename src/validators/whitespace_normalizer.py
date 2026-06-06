"""Collapses runs of whitespace to a single space and strips the ends."""
from src.validators.text_normalizer import TextNormalizer


class WhitespaceNormalizer(TextNormalizer):
    """Replaces every whitespace run with one space; trims leading/trailing whitespace."""

    def normalize(self, text: str) -> str:
        return " ".join(text.split())
