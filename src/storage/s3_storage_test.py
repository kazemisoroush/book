"""Tests for the S3-backed Storage, using moto to fake S3."""
import boto3
import pytest
from moto import mock_aws

from src.storage.keys import UnsafeKeyError
from src.storage.s3_storage import S3Storage

_BUCKET = "book-test"


@pytest.fixture
def storage():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=_BUCKET)
        yield S3Storage(bucket=_BUCKET, client=client)


def test_write_then_read_text(storage):
    # Arrange / Act
    storage.write_text("the_gambler/book.json", '{"ok": true}')

    # Assert
    assert storage.read_text("the_gambler/book.json") == '{"ok": true}'


def test_exists_and_size(storage):
    # Arrange
    storage.write_bytes("a/b.txt", b"abc")

    # Assert
    assert storage.exists("a/b.txt")
    assert storage.size("a/b.txt") == 3
    assert not storage.exists("missing")
    assert storage.size("missing") == 0


def test_empty_object_is_not_present(storage):
    # Arrange
    storage.write_bytes("empty", b"")

    # Assert (non-empty semantics, matching LocalStorage)
    assert not storage.exists("empty")


def test_list_prefix_returns_sorted_relative_keys(storage):
    # Arrange
    storage.write_bytes("bk/book.json", b"{}")
    storage.write_bytes("bk/ai/r.json", b"{}")
    storage.write_bytes("other/x", b"{}")

    # Act / Assert
    assert storage.list_prefix("bk/") == ["bk/ai/r.json", "bk/book.json"]


def test_read_missing_raises(storage):
    # Act / Assert
    with pytest.raises(FileNotFoundError):
        storage.read_bytes("nope")


def test_delete_is_idempotent_but_can_be_strict(storage):
    # Arrange
    storage.write_bytes("x", b"1")

    # Act / Assert
    storage.delete("x")
    assert not storage.exists("x")
    storage.delete("x")
    with pytest.raises(FileNotFoundError):
        storage.delete("x", missing_ok=False)


def test_local_path_downloads_for_read_and_uploads_for_write(storage):
    # Arrange
    storage.write_bytes("in.txt", b"hello")

    # Act
    with storage.local_path("in.txt", "r") as path:
        read = path.read_bytes()
    with storage.local_path("out.txt", "w") as path:
        path.write_bytes(b"world")

    # Assert
    assert read == b"hello"
    assert storage.read_bytes("out.txt") == b"world"


def test_prefix_namespaces_object_keys():
    # Arrange
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=_BUCKET)
        storage = S3Storage(bucket=_BUCKET, prefix="books/", client=client)

        # Act
        storage.write_bytes("bk/f.txt", b"x")

        # Assert: stored under books/bk/f.txt, listed as the relative key
        assert storage.list_prefix("bk/") == ["bk/f.txt"]
        raw = client.get_object(Bucket=_BUCKET, Key="books/bk/f.txt")
        assert raw["Body"].read() == b"x"


def test_rejects_unsafe_key(storage):
    # Act / Assert
    with pytest.raises(UnsafeKeyError):
        storage.write_bytes("../escape", b"x")
