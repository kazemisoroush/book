"""Utilities for generating stable, filesystem-safe book identifiers.

A ``book_id`` is a human-readable directory name derived from the book's
metadata: ``{Title} - {Author}``.  Characters that are unsafe for
filesystems (``:``, ``/``, ``\\``, ``<``, ``>``, ``"``, ``|``, ``?``,
``*``) are replaced with ``-``.
"""
import re

from src.domain.models import BookMetadata

_UNSAFE_CHARS = re.compile(r'[:/\\<>"|?*]')


def generate_book_id(metadata: BookMetadata) -> str:
    """Derive a stable, human-readable book identifier from *metadata*.

    Format: ``{title} - {author}`` with filesystem-unsafe characters
    replaced by ``-``.  If the author is ``None``, ``"Unknown"`` is used.
    """
    title = metadata.title or "Untitled"
    author = metadata.author or "Unknown"
    raw = f"{title} - {author}"
    return _UNSAFE_CHARS.sub("-", raw)
