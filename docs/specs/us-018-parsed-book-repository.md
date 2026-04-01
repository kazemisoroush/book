# US-018 — Parsed Book Repository (AI Token Savings)

## Goal

Persist the fully-parsed `Book` model to a file-based repository after the
AI parse completes, and load it on subsequent runs instead of re-invoking the
AI pipeline. This eliminates redundant AI calls when the parser has not
changed and the same book is being processed again.

---

## Background / motivation

Every run of the pipeline calls the AI section parser for every chapter, even
when nothing has changed. Each AI call costs tokens and adds latency. For
iterative work on downstream stages (voice assignment, TTS synthesis, ambient
sound, background music), the parsed model is identical run over run.

A repository layer between parsing and TTS solves this: parse once, persist,
and reuse until the user explicitly requests a re-parse. The repository is
file-based today but coded against an interface so it can be swapped for a
database later without touching callers.

---

## Acceptance criteria

### 1. `BookRepository` interface

New `src/repository/book_repository.py` defines an abstract interface:

```python
class BookRepository(ABC):
    @abstractmethod
    def save(self, book: Book, book_id: str) -> None: ...

    @abstractmethod
    def load(self, book_id: str) -> Optional[Book]: ...

    @abstractmethod
    def exists(self, book_id: str) -> bool: ...
```

`book_id` is a stable, human-readable directory name derived from the
book's metadata: `{Title} - {Author}` (e.g. `Pride and Prejudice - Jane Austen`).
Characters unsafe for filesystems are stripped or replaced.

### 2. `FileBookRepository` implementation

New `src/repository/file_book_repository.py` implements `BookRepository`:

- Persists the `Book` as JSON (using `Book.to_dict()`) to
  `{base_dir}/{book_id}/book.json`.
- Loads with `Book.from_dict()`.
- `exists()` checks whether the JSON file is present and non-empty.
- `base_dir` defaults to `./books/` in the project root but is
  configurable via constructor parameter.

Example on-disk layout:
```
books/
  Pride and Prejudice - Jane Austen/
    book.json
  A Christmas Carol - Charles Dickens/
    book.json
```

### 3. Workflow integration

`AIProjectGutenbergWorkflow` accepts an optional `BookRepository`. On `run()`:

- If the repository has a cached book for this `book_id` **and** the
  `--reparse` flag is not set, load and return it. Log at `INFO`:
  `"Loaded cached parsed book"`.
- Otherwise, run the full AI parse pipeline as today, then `save()` the
  result before returning. Log at `INFO`: `"Saved parsed book to repository"`.

`TTSProjectGutenbergWorkflow` benefits automatically because it delegates
to `AIProjectGutenbergWorkflow`.

### 4. `--reparse` CLI flag

`scripts/run_workflow.py` gains a `--reparse` flag (default `False`). When
set, the workflow skips the cache lookup and runs the full AI parse,
overwriting the cached result.

`make verify` does **not** pass `--reparse` by default. Add a separate
Make target:

```makefile
reparse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --output $(OUTPUT) \
	    --chapters $(CHAPTERS) --workflow $(WORKFLOW) --reparse
```

### 5. Cache directory in `.gitignore`

`books/` is added to `.gitignore`.

### 6. `Book.to_dict()` / `Book.from_dict()` round-trip fidelity

The existing `to_dict()` and `from_dict()` must round-trip losslessly — all
fields present on the model after an AI parse must survive serialisation and
deserialisation. If any fields are currently lost (e.g. newly added fields
from in-flight specs), fix them as part of this story.

### 7. Tests

- Unit test: `FileBookRepository.save()` then `load()` round-trips a `Book`.
- Unit test: `load()` returns `None` when no file exists.
- Unit test: `exists()` returns `True` after `save()`, `False` before.
- Unit test: workflow uses cached book when repository returns one (0 AI
  parser calls — 1 mock on the section parser to verify it is **not** called).
- Unit test: workflow calls AI parser when `reparse=True` even if cache
  exists.

---

## Out of scope

- Database-backed repository (future — the interface supports it).
- Cache invalidation based on parser version or model hash (the `--reparse`
  flag is the manual invalidation mechanism for now).
- Partial caching (per-chapter) — the full book is the unit of cache.
- Cache sharing across machines or CI.

---

## Key design decisions

### File-based, interface-backed
A file repository is trivial to implement and debug (`cat book.json`). The
abstract `BookRepository` interface means a database implementation can be
added later without changing any workflow code.

### `--reparse` over automatic invalidation
Detecting whether the parser has changed (code diff, model version, prompt
changes) is fragile and complex. A simple explicit flag gives the user full
control and is easy to understand. If nothing changed, don't reparse.

### `book_id` from metadata, not URL
Using `{Title} - {Author}` as the directory name makes the cache
browsable by humans (`ls books/`). The metadata is available after the
download-and-parse-metadata step but before the expensive AI parse, so the
workflow can check the cache before invoking AI. Filesystem-unsafe
characters (`:`, `/`, `\`, etc.) are stripped or replaced with `-`.

### `books/` not `output/`
Cache and output are different concerns. Output is what the user asked for;
cache is an optimisation artefact. Keeping them separate avoids confusion
and makes `rm -rf books/` a safe "clear all caches" operation.

---

## Files expected to change

| File | Change |
|---|---|
| `src/repository/__init__.py` | New package |
| `src/repository/book_repository.py` | Abstract `BookRepository` interface |
| `src/repository/file_book_repository.py` | File-based implementation |
| `src/repository/file_book_repository_test.py` | Unit tests for file repository |
| `src/workflows/ai_project_gutenberg_workflow.py` | Accept optional repository; cache-or-parse logic |
| `src/workflows/ai_project_gutenberg_workflow_test.py` | Tests for cache hit / miss / reparse |
| `scripts/run_workflow.py` | Add `--reparse` flag; wire repository |
| `Makefile` | Add `reparse` target |
| `.gitignore` | Add `.book_cache/` |
