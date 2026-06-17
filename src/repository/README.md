# Repository

Persistence layer for caching fully-parsed ``Book`` models and the
per-chapter LLM artifacts. Both stores delegate IO to a [Storage](../storage/storage.py) backend.

## BookRepository

`save(book)` / `save_chapter(book, chapter)` / `load(book_id)` / `exists(book_id)` plus `save_input(book)` / `load_input(book_id)` for the pre-AI snapshot. Abstract so the storage backend can be swapped (filesystem today, database later) without changing callers. `save()` derives the id from `Book.book_id`; `load()` / `exists()` take a `book_id` directly so callers can probe the cache before having a `Book`. `save_chapter(book, chapter)` is called once per parsed chapter by [AIWorkflow](../workflows/ai_workflow.py); backends with full-book state delegate to `save(book)`, backends with per-chapter content use the chapter as the unit of update.

Every workflow accepts a `repositories: list[BookRepository]`. Reads use `repositories[0]`; writes fan out to every repository in the list. Today the factory wires `[FileBookRepository]`; the list is the seam an additional per-chapter backend would plug into.

### FileBookRepository

File-based implementation that writes two JSON files per book under `{base_dir}/{book_id}/`:

* `metadata.json` is the pre-AI snapshot saved by `save_input(book)`. Contains the parsed metadata and deterministic chapters and sections before any LLM call.
* `book.json` is the final snapshot saved by `save(book)` after the AI workflow has merged beats and characters. Loaded back via `load(book_id)`. `save_chapter(book, chapter)` re-writes the same `book.json`.

`base_dir` defaults to `./books/`.

## AIArtifactStore

`save_prompt(book_id, chapter_number, prompt)` / `save_response(book_id, chapter_number, response)` for capturing the per-chapter LLM input and raw output during `AIWorkflow.run`.

### FileAIArtifactStore

File-based implementation that writes under `{base_dir}/{book_id}/ai/chapter_{NNN}/`:

* `prompt.md` is the rendered prompt string passed to the LLM.
* `response.json` is the raw JSON response, pretty-printed when valid.

## book_id

`Book.book_id` (and `BookMetadata.book_id`) is a `@property` that derives a stable, human-readable directory name from `{title}:{author}` with filesystem-unsafe characters replaced. Used by `AIWorkflow` to skip redundant AI calls on repeat runs.
