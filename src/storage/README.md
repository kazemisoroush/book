# Storage

Key-addressed object store. Every file or mp3 the pipeline writes goes through this seam so that swapping the local filesystem for S3 (or any other backend) means implementing one interface.

## Storage

Abstract base. Keys are forward-slash paths relative to the backend root.

- `read_bytes(key)` / `write_bytes(key, data)`
- `read_text(key)` / `write_text(key, text)`
- `exists(key)` — True only for non-empty objects, mirroring how the pipeline treats cache hits
- `size(key)` — 0 when missing
- `delete(key, missing_ok=True)`
- `list_prefix(prefix)` — every nested key under a prefix
- `local_path(key, mode)` — context manager yielding a real filesystem `Path`. For local backends it is the path itself; for a future S3 backend `r` downloads before yielding and `w` uploads on exit. This is the escape hatch for subprocess tools (`ffmpeg`, `ffprobe`) and libraries that write to a file path (`torchaudio.save`).

## LocalStorage

Filesystem-backed implementation. Owns all `open`, `mkdir`, `unlink`, and `shutil.copyfile` calls in one place. Construct with the base directory the keys are relative to.

```python
storage = LocalStorage(Path("books"))
storage.write_text("pride_and_prejudice/book.json", json_str)
with storage.local_path("pride_and_prejudice/audio/tts/elevenlabs_v2/beat_0001.mp3", "w") as p:
    run_ffmpeg(["-o", str(p), ...])
```

## Higher-level stores

- [BookRepository](../repository/book_repository.py): book JSON snapshots
- [AIArtifactStore](../repository/ai_artifact_store.py): per-chapter prompt and response
- [APIArtifactStore](../repository/api_artifact_store.py): one outbound API call per artifact
- [AudioStore](audio_store.py): keys and IO for TTS, SFX, dialogue chunks, silence clips, and final mix outputs

Each composes a `Storage` and adds its own key layout. To target S3, write one `S3Storage` and rewire `workflow_factory`.
