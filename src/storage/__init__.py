"""Storage primitives that abstract bytes/text IO behind a swappable backend."""
from src.storage.local_file_storage import LocalStorageBackend
from src.storage.storage import StorageBackend

__all__ = ["LocalStorageBackend", "StorageBackend"]
