"""Filesystem-backed Storage implementation."""
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.storage.keys import ensure_safe_key
from src.storage.storage import LocalPathMode, Storage


class LocalStorage(Storage):
    """Maps keys to files under *base_dir* on the local filesystem."""

    def __init__(self, base_dir: Path | str) -> None:
        self._base_dir = Path(base_dir)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def read_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def write_bytes(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read_text(self, key: str, encoding: str = "utf-8") -> str:
        return self._resolve(key).read_text(encoding=encoding)

    def write_text(self, key: str, text: str, encoding: str = "utf-8") -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)

    def exists(self, key: str) -> bool:
        path = self._resolve(key)
        if not path.is_file():
            return False
        return path.stat().st_size > 0

    def size(self, key: str) -> int:
        path = self._resolve(key)
        if not path.is_file():
            return 0
        return path.stat().st_size

    def delete(self, key: str, missing_ok: bool = True) -> None:
        self._resolve(key).unlink(missing_ok=missing_ok)

    def list_prefix(self, prefix: str) -> list[str]:
        root = self._resolve(prefix)
        if not root.exists():
            return []
        if root.is_file():
            return [prefix]
        normalized_prefix = prefix.rstrip("/")
        keys: list[str] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self._base_dir).as_posix()
            keys.append(relative if not normalized_prefix else relative)
        return keys

    @contextmanager
    def local_path(self, key: str, mode: LocalPathMode) -> Iterator[Path]:
        path = self._resolve(key)
        if mode in ("w", "rw"):
            path.parent.mkdir(parents=True, exist_ok=True)
        yield path

    def copy_within(self, src_key: str, dst_key: str) -> None:
        """Copy *src_key* to *dst_key* without going through Python buffers."""
        src = self._resolve(src_key)
        dst = self._resolve(dst_key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    def _resolve(self, key: str) -> Path:
        ensure_safe_key(key)
        return self._base_dir / key
