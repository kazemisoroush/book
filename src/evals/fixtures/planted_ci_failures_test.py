"""Tests for planted_ci_failures — planted by CI/CD Fixer eval.

These tests are correct. The CI/CD Fixer must NOT edit them.
It should fix the implementation to make them pass.
"""
from src.domain.planted_ci_failures_eval import (
    double_value,
    strip_markup,
    word_count,
)


class TestStripMarkup:
    """Verify markup removal — these should already pass."""

    def test_removes_html_tags(self) -> None:
        # Arrange
        text = "<b>hello</b> world"

        # Act
        result = strip_markup(text)

        # Assert
        assert result == "hello world"

    def test_plain_text_unchanged(self) -> None:
        # Arrange
        text = "no tags here"

        # Act
        result = strip_markup(text)

        # Assert
        assert result == "no tags here"


class TestWordCount:
    """Verify word count returns an integer."""

    def test_counts_words(self) -> None:
        # Arrange
        text = "one two three"

        # Act
        result = word_count(text)

        # Assert
        assert result == 3
        assert isinstance(result, int)


class TestDoubleValue:
    """Verify doubling logic."""

    def test_doubles_positive(self) -> None:
        # Arrange
        n = 7

        # Act
        result = double_value(n)

        # Assert
        assert result == 14

    def test_doubles_zero(self) -> None:
        # Arrange
        n = 0

        # Act
        result = double_value(n)

        # Assert
        assert result == 0
