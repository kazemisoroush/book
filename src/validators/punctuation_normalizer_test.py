"""Tests for PunctuationNormalizer."""
from src.validators.punctuation_normalizer import PunctuationNormalizer


def test_removes_punctuation_across_unicode_categories():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("“Hello, world!”—at last?{2}")

    # Assert
    assert result == "Hello worldat last2"


def test_letters_digits_and_whitespace_are_preserved():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("just plain words 123")

    # Assert
    assert result == "just plain words 123"
