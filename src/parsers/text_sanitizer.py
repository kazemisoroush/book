"""Pure text sanitization functions for TTS-ready beat text.

This module provides functions to clean beat text at creation time,
removing trailing punctuation artefacts that cause audible clicks or
odd inflections in TTS output.
"""

import re


def sanitize_beat_text(text: str) -> str:
    """Strip trailing non-terminal punctuation and normalise whitespace.

    Args:
        text: Raw beat text from AI parser

    Returns:
        Clean text ready for TTS, with:
        - Trailing whitespace removed
        - Trailing non-terminal punctuation removed (`, ; : — – - … · * # @`)
        - Terminal punctuation preserved (`. ! ? "`)
        - Internal whitespace runs collapsed to single space
        - Leading whitespace removed

    Examples:
        >>> sanitize_beat_text("My dear Mr. Bennet,")
        'My dear Mr. Bennet'
        >>> sanitize_beat_text("and so she went—")
        'and so she went'
        >>> sanitize_beat_text("Hello.")
        'Hello.'
        >>> sanitize_beat_text('"Come here,"')
        '"Come here,"'
    """
    # Step 1: Strip leading and trailing whitespace
    text = text.strip()

    # Step 2: Collapse internal whitespace runs to single space
    text = re.sub(r'\s+', ' ', text)

    # Step 3: Strip trailing non-terminal punctuation
    # Repeat until string ends with word character or terminal punctuation
    # Non-terminal: , ; : — – - … · * # @ and Unicode variants
    # Terminal: . ! ? "
    non_terminal_punct = r'[,;:\u2014\u2013\-\u2026\u00b7\*#@]'

    while text:
        # If ends with terminal punctuation or word character, done
        if re.search(r'[\w.!?"]$', text):
            break
        # If ends with non-terminal punctuation, strip it
        if re.search(non_terminal_punct + r'$', text):
            text = re.sub(non_terminal_punct + r'$', '', text)
            # Strip any trailing whitespace that was behind the punctuation
            text = text.rstrip()
        else:
            # Ends with something else (shouldn't happen, but break to avoid infinite loop)
            break

    return text
