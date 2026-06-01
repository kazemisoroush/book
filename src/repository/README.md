# Repository

Persistence layer for caching fully-parsed ``Book`` models.

## BookRepository

`save(book)` / `load(book_id)` / `exists(book_id)` — abstract interface so the storage backend can be swapped (filesystem today, database later) without changing callers. `save()` derives the id from `Book.book_id`; `load()` / `exists()` take a `book_id` directly so callers can probe the cache before having a `Book`.

### FileBookRepository

File-based implementation; persists `Book.to_dict()` as JSON to `{base_dir}/{book.book_id}/book.json`; `base_dir` defaults to `./books/`.

## book_id

`Book.book_id` (and `BookMetadata.book_id`) is a `@property` that derives a stable, human-readable directory name from `{Title} - {Author}` with filesystem-unsafe characters replaced by `-`. Used by `AIWorkflow` to skip redundant AI calls on repeat runs.
