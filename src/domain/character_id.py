"""Helpers for building stable character IDs scoped to a book."""
import re

_UNSAFE_NAME = re.compile(r"[^a-z0-9]+")


def slugify_name(name: str) -> str:
    """Lowercase *name* and collapse non-alphanumeric runs to underscores."""
    return _UNSAFE_NAME.sub("_", name.strip().lower()).strip("_")


def build_character_id(book_id: str, name: str) -> str:
    """Return ``{book_id}:{name_slug}`` for a character in *book_id*."""
    return f"{book_id}:{slugify_name(name)}"
