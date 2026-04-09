"""TextStats utility for computing text statistics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextStats:
    """Statistics about a text.

    Attributes:
        word_count: Number of words (split on whitespace)
        sentence_count: Number of sentences (split on . ! ?)
        avg_word_length: Mean character count per word, rounded to 1 decimal
    """
    word_count: int
    sentence_count: int
    avg_word_length: float


def compute_text_stats(text: str) -> TextStats:
    """Compute statistics for the given text.

    Args:
        text: The text to analyze

    Returns:
        TextStats with word count, sentence count, and average word length
    """
    # Split into words on whitespace
    words = text.split()
    word_count = len(words)

    # Compute average word length
    if word_count == 0:
        avg_word_length = 0.0
    else:
        total_chars = sum(len(word) for word in words)
        avg_word_length = round(total_chars / word_count, 1)

    # Count sentences by splitting on sentence delimiters
    # Replace all delimiters with a common one, then split
    temp_text = text
    for delimiter in ['!', '?']:
        temp_text = temp_text.replace(delimiter, '.')

    # Split on period and count non-empty segments
    segments = temp_text.split('.')
    sentence_count = sum(1 for segment in segments if segment.strip())

    return TextStats(
        word_count=word_count,
        sentence_count=sentence_count,
        avg_word_length=avg_word_length,
    )
