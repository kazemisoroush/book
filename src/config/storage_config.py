"""Configuration for the storage backend."""
import os
from dataclasses import dataclass
from enum import Enum


class StorageBackend(str, Enum):
    """The storage backends the pipeline can run against."""
    LOCAL = 'local'
    S3 = 's3'


@dataclass
class StorageConfig:
    """Which storage backend to use, and the S3 location when remote."""
    backend: StorageBackend
    bucket: str = ""
    prefix: str = ""

    @classmethod
    def from_env(cls) -> 'StorageConfig':
        """Load the storage backend selection from environment variables."""
        return cls(
            backend=StorageBackend(os.getenv('BOOK_STORAGE', StorageBackend.LOCAL.value)),
            bucket=os.getenv('BOOK_S3_BUCKET', ''),
            prefix=os.getenv('BOOK_S3_PREFIX', ''),
        )
