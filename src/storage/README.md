# Storage

Key-addressed object store. Every file the higher-level stores write goes through this seam, so swapping the local filesystem for S3 is a matter of which backend is selected.

## Backend

Abstract key-and-bytes interface for reading, writing, listing, and deleting objects, plus `local_path` which yields a real filesystem path for subprocess tools. Keys are validated by `ensure_safe_key`, so no key can escape the storage root.

## Local backend

Filesystem-backed implementation. Construct with the base directory the keys are relative to.

## S3 backend

`s3_storage.py` maps keys to objects in an S3 bucket under an optional prefix. It honors the `local_path` contract for a remote backend: `r` downloads the object to a temp file, `w` uploads the written temp file on exit, and `rw` does both, so `ffmpeg` and file serving keep working against S3.

## Selecting a backend

`create_storage(base_dir)` returns the backend chosen by `StorageConfig` (`src/config/storage_config.py`), driven by environment only:

- `BOOK_STORAGE` is `local` (default) or `s3`.
- `BOOK_S3_BUCKET` and `BOOK_S3_PREFIX` locate the bucket when `s3`.

The repositories and the API build their storage through this factory, so setting `BOOK_STORAGE=s3` switches the whole pipeline with no code change.
