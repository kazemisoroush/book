"""S3-backed Storage implementation."""
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from src.storage.keys import ensure_safe_key
from src.storage.storage import LocalPathMode, Storage


class S3Storage(Storage):
    """Maps keys to objects in an S3 bucket under an optional prefix."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        client: Optional[Any] = None,
    ) -> None:
        if client is None:
            import boto3
            client = boto3.client("s3")
        self._bucket = bucket
        self._prefix = prefix
        self._client = client

    def read_bytes(self, key: str) -> bytes:
        try:
            response = self._client.get_object(
                Bucket=self._bucket, Key=self._object_key(key),
            )
        except self._client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(key) from exc
        data: bytes = response["Body"].read()
        return data

    def write_bytes(self, key: str, data: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=self._object_key(key), Body=data,
        )

    def read_text(self, key: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(key).decode(encoding)

    def write_text(self, key: str, text: str, encoding: str = "utf-8") -> None:
        self.write_bytes(key, text.encode(encoding))

    def exists(self, key: str) -> bool:
        size = self._head_size(key)
        return size is not None and size > 0

    def size(self, key: str) -> int:
        return self._head_size(key) or 0

    def delete(self, key: str, missing_ok: bool = True) -> None:
        if not missing_ok and self._head_size(key) is None:
            raise FileNotFoundError(key)
        self._client.delete_object(Bucket=self._bucket, Key=self._object_key(key))

    def list_prefix(self, prefix: str) -> list[str]:
        ensure_safe_key(prefix)
        object_prefix = self._object_key(prefix)
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=object_prefix):
            for item in page.get("Contents", []):
                keys.append(item["Key"][len(self._prefix):])
        return sorted(keys)

    @contextmanager
    def local_path(self, key: str, mode: LocalPathMode) -> Iterator[Path]:
        ensure_safe_key(key)
        tmpdir = tempfile.mkdtemp()
        try:
            path = Path(tmpdir) / (Path(key).name or "object")
            if mode in ("r", "rw"):
                path.write_bytes(self.read_bytes(key))
            yield path
            if mode in ("w", "rw") and path.exists():
                self.write_bytes(key, path.read_bytes())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _object_key(self, key: str) -> str:
        ensure_safe_key(key)
        return f"{self._prefix}{key}"

    def _head_size(self, key: str) -> Optional[int]:
        try:
            response = self._client.head_object(
                Bucket=self._bucket, Key=self._object_key(key),
            )
        except self._client.exceptions.ClientError:
            return None
        length: int = response["ContentLength"]
        return length
