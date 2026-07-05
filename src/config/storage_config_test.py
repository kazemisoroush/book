"""Tests for the storage backend configuration."""
import pytest

from src.config.storage_config import StorageBackend, StorageConfig


def test_defaults_to_local(monkeypatch):
    # Arrange
    monkeypatch.delenv("BOOK_STORAGE", raising=False)

    # Act
    config = StorageConfig.from_env()

    # Assert
    assert config.backend is StorageBackend.LOCAL


def test_reads_s3_settings(monkeypatch):
    # Arrange
    monkeypatch.setenv("BOOK_STORAGE", "s3")
    monkeypatch.setenv("BOOK_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("BOOK_S3_PREFIX", "books/")

    # Act
    config = StorageConfig.from_env()

    # Assert
    assert (config.backend, config.bucket, config.prefix) == (
        StorageBackend.S3, "my-bucket", "books/",
    )


def test_rejects_unknown_backend(monkeypatch):
    # Arrange
    monkeypatch.setenv("BOOK_STORAGE", "ftp")

    # Act / Assert
    with pytest.raises(ValueError):
        StorageConfig.from_env()
