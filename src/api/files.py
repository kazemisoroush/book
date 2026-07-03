"""Safe path resolution and key helpers for files under the books directory."""
from pathlib import Path


class PathOutsideBookError(Exception):
    """Raised when a requested path escapes the book directory."""


def book_ids_from_keys(keys: list[str]) -> list[str]:
    """Return the distinct top-level book ids from a list of storage keys."""
    ids = {
        key.split("/", 1)[0]
        for key in keys
        if "/" in key and not key.startswith(".")
    }
    return sorted(ids)


def resolve_within(book_dir: Path, relative_path: str) -> Path:
    """Resolve *relative_path* inside *book_dir* and reject any escape."""
    base = book_dir.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise PathOutsideBookError(relative_path)
    return target


def resolve_book_dir(books_dir: Path, book_id: str) -> Path:
    """Resolve *book_id* to a direct child of *books_dir* and reject any escape."""
    base = books_dir.resolve()
    target = (base / book_id).resolve()
    if target.parent != base:
        raise PathOutsideBookError(book_id)
    return target
