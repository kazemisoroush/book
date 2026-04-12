"""Tests for planted doc drift module.

Exercises all public functions so the Doc Auditor sees them as live code.
"""
from src.domain.planted_doc_drift_eval import (
    split_into_sentences,
    count_words,
    merge_chunks,
    deduplicate_chunks,
)


class TestSplitIntoSentences:
    """Tests for split_into_sentences."""

    def test_splits_on_periods(self) -> None:
        """Splits text at period boundaries."""
        # Arrange
        text = "Hello world. Goodbye world."

        # Act
        result = split_into_sentences(text)

        # Assert
        assert result == ["Hello world", "Goodbye world"]


class TestCountWords:
    """Tests for count_words."""

    def test_counts_words(self) -> None:
        """Returns correct word count."""
        # Arrange / Act
        result = count_words("hello world foo")

        # Assert
        assert result == 3


class TestMergeChunks:
    """Tests for merge_chunks."""

    def test_joins_with_space(self) -> None:
        """Merges chunks with space separator."""
        # Arrange / Act
        result = merge_chunks(["hello", "world"])

        # Assert
        assert result == "hello world"


class TestDeduplicateChunks:
    """Tests for deduplicate_chunks."""

    def test_removes_duplicates(self) -> None:
        """Removes duplicates preserving order."""
        # Arrange / Act
        result = deduplicate_chunks(["a", "b", "a", "c", "b"])

        # Assert
        assert result == ["a", "b", "c"]
