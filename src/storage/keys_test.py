"""Tests for pure storage key-safety helpers."""
import pytest

from src.storage.keys import UnsafeKeyError, book_ids_from_keys, ensure_safe_key


def test_ensure_safe_key_returns_relative_key():
    # Arrange
    key = "the_gambler/book.json"

    # Act
    result = ensure_safe_key(key)

    # Assert
    assert result == key


def test_ensure_safe_key_allows_empty_and_trailing_slash():
    # Act / Assert
    assert ensure_safe_key("") == ""
    assert ensure_safe_key("the_gambler/") == "the_gambler/"


@pytest.mark.parametrize("key", ["../secret", "the_gambler/../../etc", "a/../b"])
def test_ensure_safe_key_rejects_traversal(key):
    # Act / Assert
    with pytest.raises(UnsafeKeyError):
        ensure_safe_key(key)


def test_ensure_safe_key_rejects_absolute():
    # Act / Assert
    with pytest.raises(UnsafeKeyError):
        ensure_safe_key("/etc/passwd")


def test_book_ids_from_keys_dedupes_and_skips_hidden():
    # Arrange
    keys = [
        "the_gambler/book.json",
        "the_gambler/ai/response.json",
        "dracula/book.json",
        ".runs/abc/status.json",
    ]

    # Act
    ids = book_ids_from_keys(keys)

    # Assert
    assert ids == ["dracula", "the_gambler"]
