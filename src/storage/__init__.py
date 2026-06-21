"""Storage primitives that abstract bytes/text IO behind a swappable backend."""
from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage

__all__ = ["LocalStorage", "Storage"]
