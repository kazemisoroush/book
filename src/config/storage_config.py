"""Configuration for the storage backend."""
import os
from dataclasses import dataclass


@dataclass
class StorageConfig:
    """Which storage backend to use, and the S3 location when remote."""
    backend: str
    bucket: str = ""
    prefix: str = ""

    @classmethod
    def from_env(cls) -> 'StorageConfig':
        """Load the storage backend selection from environment variables."""
        return cls(
            backend=os.getenv('BOOK_STORAGE', 'local'),
            bucket=os.getenv('BOOK_S3_BUCKET', ''),
            prefix=os.getenv('BOOK_S3_PREFIX', ''),
        )
