"""Safe listing and path resolution for files under a book directory."""
from pathlib import Path


class PathOutsideBookError(Exception):
    """Raised when a requested path escapes the book directory."""


def list_book_ids(books_dir: Path) -> list[str]:
    """Return the book ids, one per non-hidden directory under *books_dir*."""
    if not books_dir.is_dir():
        return []
    ids = [
        entry.name
        for entry in books_dir.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    ]
    return sorted(ids)


def list_files(book_dir: Path) -> list[str]:
    """Return every file under *book_dir* as a sorted list of relative paths."""
    if not book_dir.is_dir():
        return []
    files = [
        str(path.relative_to(book_dir))
        for path in book_dir.rglob("*")
        if path.is_file()
    ]
    return sorted(files)


def resolve_within(book_dir: Path, relative_path: str) -> Path:
    """Resolve *relative_path* inside *book_dir* and reject any escape."""
    base = book_dir.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise PathOutsideBookError(relative_path)
    return target
