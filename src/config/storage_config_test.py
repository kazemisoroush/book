"""Tests for the storage backend configuration."""
from src.config.storage_config import StorageConfig


def test_defaults_to_local(monkeypatch):
    # Arrange
    monkeypatch.delenv("BOOK_STORAGE", raising=False)

    # Act
    config = StorageConfig.from_env()

    # Assert
    assert config.backend == "local"


def test_reads_s3_settings(monkeypatch):
    # Arrange
    monkeypatch.setenv("BOOK_STORAGE", "s3")
    monkeypatch.setenv("BOOK_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("BOOK_S3_PREFIX", "books/")

    # Act
    config = StorageConfig.from_env()

    # Assert
    assert (config.backend, config.bucket, config.prefix) == (
        "s3", "my-bucket", "books/",
    )
