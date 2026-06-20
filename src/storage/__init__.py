"""Storage primitives that abstract bytes/text IO behind a swappable backend."""
from src.storage.local_file_storage import LocalFileStorage
from src.storage.storage import Storage

__all__ = ["LocalFileStorage", "Storage"]
