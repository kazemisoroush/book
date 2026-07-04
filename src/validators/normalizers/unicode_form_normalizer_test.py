"""Tests for UnicodeFormNormalizer."""
import unicodedata

from src.validators.normalizers.unicode_form_normalizer import UnicodeFormNormalizer


def test_decomposed_accents_become_composed():
    # Arrange
    normalizer = UnicodeFormNormalizer()
    decomposed = unicodedata.normalize("NFD", "naïve protégé rôle")

    # Act
    result = normalizer.normalize(decomposed)

    # Assert
    assert result == unicodedata.normalize("NFC", "naïve protégé rôle")


def test_composed_and_decomposed_forms_normalize_equal():
    # Arrange
    normalizer = UnicodeFormNormalizer()
    composed = unicodedata.normalize("NFC", "De Grieux")
    decomposed = unicodedata.normalize("NFD", "De Grieux")

    # Act
    result_composed = normalizer.normalize(composed)
    result_decomposed = normalizer.normalize(decomposed)

    # Assert
    assert result_composed == result_decomposed


def test_plain_ascii_text_is_unchanged():
    # Arrange
    normalizer = UnicodeFormNormalizer()

    # Act
    result = normalizer.normalize("the gambler 4000 gulden")

    # Assert
    assert result == "the gambler 4000 gulden"
