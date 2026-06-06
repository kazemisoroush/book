"""Tests for LowercaseNormalizer."""
from src.validators.lowercase_normalizer import LowercaseNormalizer


def test_lowercases_ascii_and_unicode_uppercase():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("Hello ÀÇÉ")

    # Assert
    assert result == "hello àçé"


def test_already_lowercase_text_is_unchanged():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("hello world 123")

    # Assert
    assert result == "hello world 123"
