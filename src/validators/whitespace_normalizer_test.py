"""Tests for WhitespaceNormalizer."""
from src.validators.whitespace_normalizer import WhitespaceNormalizer


def test_collapses_double_spaces():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("hello  world")

    # Assert
    assert result == "hello world"


def test_collapses_tabs_and_newlines():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("hello\tworld\n\nfoo")

    # Assert
    assert result == "hello world foo"


def test_strips_leading_and_trailing_whitespace():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("   hello world   ")

    # Assert
    assert result == "hello world"


def test_single_space_is_unchanged():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("hello world")

    # Assert
    assert result == "hello world"


def test_whitespace_only_becomes_empty():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("   \t\n  ")

    # Assert
    assert result == ""


def test_empty_string():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("")

    # Assert
    assert result == ""
