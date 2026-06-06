"""Tests for LowercaseNormalizer."""
from src.validators.lowercase_normalizer import LowercaseNormalizer


def test_uppercase_becomes_lowercase():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("Hello World")

    # Assert
    assert result == "hello world"


def test_all_caps_becomes_lowercase():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("SOMEWHERE")

    # Assert
    assert result == "somewhere"


def test_already_lowercase_unchanged():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("hello world")

    # Assert
    assert result == "hello world"


def test_unicode_uppercase_is_lowered():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("ÀÇÉ")

    # Assert
    assert result == "àçé"


def test_digits_and_punctuation_unchanged():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("123 ABC, def!")

    # Assert
    assert result == "123 abc, def!"


def test_empty_string():
    # Arrange
    normalizer = LowercaseNormalizer()

    # Act
    result = normalizer.normalize("")

    # Assert
    assert result == ""
