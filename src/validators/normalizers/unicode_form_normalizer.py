"""Normalizes text to Unicode NFC so accents match regardless of encoding form."""
import unicodedata

from src.validators.normalizers.text_normalizer import TextNormalizer


class UnicodeFormNormalizer(TextNormalizer):
    """Rewrites text to Unicode NFC so composed and decomposed accents compare equal."""

    def normalize(self, text: str) -> str:
        return unicodedata.normalize("NFC", text)
