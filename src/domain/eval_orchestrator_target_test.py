"""Tests for TextStats utility."""

import pytest

from src.domain.eval_orchestrator_target import TextStats, compute_text_stats


class TestTextStatsDataclass:
    """Tests for TextStats dataclass structure."""

    def test_textstats_is_frozen(self) -> None:
        """TextStats should be immutable."""
        stats = TextStats(word_count=5, sentence_count=2, avg_word_length=4.5)
        with pytest.raises(Exception):  # FrozenInstanceError
            stats.word_count = 10  # type: ignore[misc]


class TestComputeTextStatsEmpty:
    """Tests for empty/edge case inputs."""

    def test_empty_string_returns_zero_stats(self) -> None:
        """Empty string should return all zeros."""
        result = compute_text_stats("")
        assert result.word_count == 0
        assert result.sentence_count == 0
        assert result.avg_word_length == 0.0

    def test_whitespace_only_returns_zero_stats(self) -> None:
        """Whitespace-only string should return zero word count."""
        result = compute_text_stats("   \n\t  ")
        assert result.word_count == 0
        assert result.avg_word_length == 0.0


class TestComputeTextStatsSentences:
    """Tests for sentence counting."""

    def test_single_sentence_with_period(self) -> None:
        """Single sentence ending with period."""
        result = compute_text_stats("Hello world.")
        assert result.sentence_count == 1

    def test_multiple_sentences_with_mixed_delimiters(self) -> None:
        """Multiple sentences with different delimiters."""
        result = compute_text_stats("First sentence. Second? Third!")
        assert result.sentence_count == 3

    def test_empty_splits_ignored(self) -> None:
        """Multiple delimiters in a row should not create empty sentences."""
        result = compute_text_stats("Hello... World!!")
        # "Hello" and " World" are two sentences (delimiters create splits)
        # Empty strings from multiple delimiters should be ignored
        assert result.sentence_count == 2

    def test_no_sentence_delimiters(self) -> None:
        """Text without sentence delimiters is one sentence."""
        result = compute_text_stats("no delimiters here")
        assert result.sentence_count == 1


class TestComputeTextStatsWords:
    """Tests for word counting and average length."""

    def test_single_word(self) -> None:
        """Single word."""
        result = compute_text_stats("Hello")
        assert result.word_count == 1
        assert result.avg_word_length == 5.0

    def test_multiple_words_with_spaces(self) -> None:
        """Multiple words separated by spaces."""
        result = compute_text_stats("one two three")
        assert result.word_count == 3
        # "one"=3, "two"=3, "three"=5 -> (3+3+5)/3 = 3.666... -> 3.7
        assert result.avg_word_length == 3.7

    def test_words_with_mixed_whitespace(self) -> None:
        """Words separated by tabs and newlines."""
        result = compute_text_stats("one\ttwo\nthree")
        assert result.word_count == 3

    def test_average_word_length_rounded_to_one_decimal(self) -> None:
        """Average word length should be rounded to 1 decimal place."""
        # "ab"=2, "cde"=3 -> (2+3)/2 = 2.5
        result = compute_text_stats("ab cde")
        assert result.word_count == 2
        assert result.avg_word_length == 2.5

    def test_average_word_length_rounding(self) -> None:
        """Test proper rounding behavior."""
        # "a"=1, "bb"=2, "ccc"=3 -> (1+2+3)/3 = 2.0
        result = compute_text_stats("a bb ccc")
        assert result.avg_word_length == 2.0


class TestComputeTextStatsIntegration:
    """Integration tests combining all features."""

    def test_full_text_with_sentences_and_words(self) -> None:
        """Complete text with multiple sentences and words."""
        text = "Hello world. How are you? I am fine!"
        result = compute_text_stats(text)

        # Arrange expected values
        # Sentences: 3 (split on . ? !)
        # Words: "Hello", "world.", "How", "are", "you?", "I", "am", "fine!"
        # Wait - words split on whitespace, so "world." is one word including the period
        # word_count = 8
        # avg_word_length = (5+6+3+3+4+1+2+5) / 8 = 29/8 = 3.625 -> 3.6

        assert result.word_count == 8
        assert result.sentence_count == 3
        assert result.avg_word_length == 3.6

    def test_text_with_only_sentence_delimiters(self) -> None:
        """Text that is only delimiters has no sentences (all splits empty)."""
        result = compute_text_stats("...!!??")
        assert result.word_count == 1  # The string "...!!??" itself is a word
        assert result.sentence_count == 0  # All splits are empty, ignored per spec
