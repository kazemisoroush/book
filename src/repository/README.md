# Repository

Persistence layer for caching fully-parsed ``Book`` models.

## BookRepository

`save(book, book_id)` / `load(book_id)` / `exists(book_id)` — abstract interface so the storage backend can be swapped (filesystem today, database later) without changing callers.

### FileBookRepository

File-based implementation; persists `Book.to_dict()` as JSON to `{base_dir}/{book_id}/book.json`; `base_dir` defaults to `./books/`.

## book_id helper

`generate_book_id(metadata)` — derives a stable, human-readable directory name from `{Title} - {Author}` with filesystem-unsafe characters replaced by `-`.

**Used by**: `AIProjectGutenbergWorkflow` to skip redundant AI calls on repeat runs.  The `--reparse` CLI flag forces a fresh parse when needed.
