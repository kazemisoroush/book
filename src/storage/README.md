# Storage

Key-addressed object store. Every file the higher-level stores write goes through this seam so swapping the local filesystem for S3 means implementing one interface.

## Storage

Key-and-bytes interface (`read_bytes` / `write_bytes`, `read_text` / `write_text`, `exists`, `size`, `delete`, `list_prefix`, `local_path`). `local_path(key, mode)` yields a real filesystem `Path` for subprocess tools like `ffmpeg`.

## LocalStorage

Filesystem-backed implementation. Owns every `open` / `mkdir` / `unlink` / `shutil.copyfile` call. Construct with the base directory the keys are relative to.

```python
storage = LocalStorage(Path("books"))
storage.write_text("pride_and_prejudice/book.json", json_str)
```

## Higher-level stores

Compose `Storage` with their own layout:

- [BookStore](../stores/book_store.py): `book.json` and `metadata.json` snapshots
- [AIArtifactStore](../stores/ai_artifact_store.py): per-chapter `prompt.md` and `response.json`

To target S3, write one `S3Storage` and rewire `workflow_factory`.
