"""Tests for the storage backend factory."""
import boto3
import pytest
from moto import mock_aws

from src.config.storage_config import StorageConfig
from src.storage.local_storage import LocalStorage
from src.storage.s3_storage import S3Storage
from src.storage.storage_factory import create_storage


def test_builds_local_backend(tmp_path):
    # Act
    storage = create_storage(tmp_path, StorageConfig(backend="local"))

    # Assert
    assert isinstance(storage, LocalStorage)


def test_s3_backend_requires_a_bucket():
    # Act / Assert
    with pytest.raises(ValueError):
        create_storage("books", StorageConfig(backend="s3", bucket=""))


def test_builds_s3_backend(monkeypatch):
    # Arrange
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="book-bucket")

        # Act
        storage = create_storage(
            "books", StorageConfig(backend="s3", bucket="book-bucket"),
        )

        # Assert
        assert isinstance(storage, S3Storage)
