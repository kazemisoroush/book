"""Build the configured Storage backend."""
from pathlib import Path
from typing import Optional, Union

from src.config.storage_config import StorageConfig
from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage


def create_storage(
    base_dir: Union[str, Path] = "books",
    config: Optional[StorageConfig] = None,
) -> Storage:
    """Return the S3 or local backend selected by *config*; *base_dir* is local only."""
    config = config or StorageConfig.from_env()
    if config.backend == "s3":
        if not config.bucket:
            raise ValueError("BOOK_S3_BUCKET must be set when BOOK_STORAGE=s3")
        from src.storage.s3_storage import S3Storage
        return S3Storage(bucket=config.bucket, prefix=config.prefix)
    return LocalStorage(base_dir)
