"""Helpers for the on-disk layout of downloaded book sources."""
import os
import re
import shutil
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_BOOKS_DIR = "books"
_STAGING_SUBDIR = ".sources"
_SOURCE_SUBDIR = "source"
_PG_ID_RE = re.compile(r"/(\d+)(?:/|$)")


def pg_id_from_url(url: str) -> str:
    """Return the Project Gutenberg numeric id parsed from *url*."""
    match = _PG_ID_RE.search(url)
    if match:
        return match.group(1)
    for part in url.split("/"):
        if part.isdigit():
            return part
    return "unknown"


def staging_dir(books_dir: str = _DEFAULT_BOOKS_DIR, pg_id: str = "") -> Path:
    """Return the staging directory under which raw downloads are extracted."""
    return Path(books_dir) / _STAGING_SUBDIR / pg_id


def book_source_dir(books_dir: str, book_id: str) -> Path:
    """Return the per-book ``source/`` directory."""
    return Path(books_dir) / book_id / _SOURCE_SUBDIR


def materialize_source(
    books_dir: str, pg_id: str, book_id: str,
) -> None:
    """Mirror the staged source into ``{books_dir}/{book_id}/source/`` once book_id is known."""
    target = book_source_dir(books_dir, book_id)
    if target.exists():
        return
    source = staging_dir(books_dir, pg_id)
    if not source.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for name in os.listdir(source):
        src = source / name
        dst = target / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    logger.info(
        "source_materialized", book_id=book_id, pg_id=pg_id, path=str(target),
    )
