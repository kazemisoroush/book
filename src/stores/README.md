# Stores

Persistence layer for caching fully-parsed ``Book`` models and observability artifacts. All stores delegate IO to a [Storage](../storage/storage.py) backend.

## BookStore

Abstract store for saving and loading ``Book`` snapshots. Workflows accept `stores: list[BookStore]`; reads use `stores[0]`, writes fan out to every store.

### FileBookStore

File-based implementation that writes `metadata.json` (pre-AI snapshot) and `book.json` (final snapshot) per book under `{base_dir}/{book_id}/`.

## ArtifactStore

Unified store for AI chapter artifacts (prompts and responses) and outbound API request records with credential redaction.

### FileArtifactStore

File-based implementation. AI artifacts go under `{book_id}/ai/{chapter.dir_slug}/`. API request records are written at caller-specified keys.
