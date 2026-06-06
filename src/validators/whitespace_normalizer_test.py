"""Tests for WhitespaceNormalizer."""
from src.validators.whitespace_normalizer import WhitespaceNormalizer


def test_collapses_runs_and_strips_ends():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("   hello\t\tworld\n\nfoo   ")

    # Assert
    assert result == "hello world foo"


def test_already_single_spaced_text_is_unchanged():
    # Arrange
    normalizer = WhitespaceNormalizer()

    # Act
    result = normalizer.normalize("hello world")

    # Assert
    assert result == "hello world"
