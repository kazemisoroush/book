"""Tests for the planted dead code module.

These tests exercise the LIVE symbols so the Dead Code Remover
can confirm they have callers. Without this file, the remover
would (correctly) flag everything as dead.

NOT a real test file. The eval scorer copies this alongside the
module at setup time.
"""
from src.domain.planted_dead_code_eval import normalize_whitespace, compute_stats, HelperResult


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace — the LIVE function."""

    def test_collapses_spaces(self) -> None:
        """Multiple spaces become one."""
        # Arrange
        text = "hello   world"

        # Act
        result = normalize_whitespace(text)

        # Assert
        assert result.text == "hello world"
        assert result.changed is True

    def test_unchanged_text(self) -> None:
        """Already-clean text reports changed=False."""
        # Arrange
        text = "hello world"

        # Act
        result = normalize_whitespace(text)

        # Assert
        assert result.text == "hello world"
        assert result.changed is False


class TestComputeStats:
    """Tests for compute_stats — the LIVE function."""

    def test_counts_words_and_chars(self) -> None:
        """Returns correct word and character counts."""
        # Arrange
        text = "hello world"

        # Act
        result = compute_stats(text)

        # Assert
        assert result == {"words": 2, "chars": 11}

    def test_empty_string(self) -> None:
        """Empty string returns zeros."""
        # Arrange / Act
        result = compute_stats("")

        # Assert
        assert result == {"words": 0, "chars": 0}
