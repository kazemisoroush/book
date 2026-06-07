"""Lowercases every character in the input text."""
from src.validators.normalizers.text_normalizer import TextNormalizer


class LowercaseNormalizer(TextNormalizer):
    """Returns the input with every character lowercased."""

    def normalize(self, text: str) -> str:
        return text.lower()
