"""Pure key-safety helpers shared by every Storage backend."""
import os


class UnsafeKeyError(ValueError):
    """Raised when a storage key is absolute or would escape the storage root."""


def ensure_safe_key(key: str) -> str:
    """Return *key* unchanged, or raise when it is absolute or escapes the root."""
    if os.path.isabs(key) or key.startswith("/"):
        raise UnsafeKeyError(f"storage keys must be relative, got {key!r}")
    if ".." in key.replace("\\", "/").split("/"):
        raise UnsafeKeyError(f"storage key escapes the root, got {key!r}")
    return key


def book_ids_from_keys(keys: list[str]) -> list[str]:
    """Return the distinct top-level book ids from a list of storage keys.

    Control directories are skipped: dot-prefixed (run state) and
    underscore-prefixed (shared caches like ``_shared_voices``) are not books.
    """
    ids = {
        key.split("/", 1)[0]
        for key in keys
        if "/" in key and not key.startswith((".", "_"))
    }
    return sorted(ids)
