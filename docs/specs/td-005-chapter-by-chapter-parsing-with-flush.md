# TD-005 — Chapter-by-Chapter Parsing with Repository Flush

## Goal

Enable resilient, long-running book processing by persisting parsed chapters to the repository immediately after each chapter completes. This prevents total loss of work when AWS credentials expire mid-run (e.g., failing at chapter 10 means chapters 1–9 are already saved).

---

## Problem

Current workflow:
- `AIProjectGutenbergWorkflow.run()` parses all chapters into memory, then saves the final `Book` to repository at the very end
- If processing fails at chapter 10 (out of 61), all 9 completed chapters are lost
- For long-running jobs (2+ hours), AWS SSO tokens expire mid-run despite credential refresh logic
- Users must restart from chapter 1, wasting hours of API calls and incurring duplicate costs

---

## Concept

**Incremental Repository Persistence**:

1. As each chapter completes parsing, immediately persist a partial `Book` snapshot to repository
2. Each snapshot contains: metadata, character registry, scene registry, and chapters 1–N (where N is the completed chapter count)
3. On restart, check if a partial book exists in the repository; if so, start from chapter N+1 instead of chapter 1
4. Final output: fully-assembled book with all 61 chapters (or requested chapter_limit)

**Implementation Pattern**:

```python
# Pseudo-code for the new workflow with start_chapter and end_chapter parameters

def run(self, url, start_chapter=1, end_chapter=None):
    """
    Parse chapters from start_chapter to end_chapter (inclusive).

    Args:
        start_chapter: 1-based chapter index to begin parsing (default: 1)
        end_chapter: 1-based chapter index to end parsing (default: last chapter)
    """
    # If resuming from cache, load partial book and adjust start_chapter
    if start_chapter == 1 and self._repository.exists(book_id):
        cached_book = self._repository.load(book_id)
        if cached_book and cached_book.content.chapters:
            last_cached_chapter = len(cached_book.content.chapters)
            book = cached_book
            start_chapter = last_cached_chapter + 1
            logger.info(f"Resuming from chapter {start_chapter} ({last_cached_chapter} already parsed)")

    # Determine end chapter (default: all chapters in book)
    if end_chapter is None:
        end_chapter = total_chapters_in_book

    # Parse from start_chapter to end_chapter
    for chapter_number in range(start_chapter, end_chapter + 1):
        parsed_chapter = parse_chapter(chapter_number)
        book.content.chapters.append(parsed_chapter)

        # Flush to repository immediately after each chapter
        if repository is not None:
            repository.save(book, book_id)

        logger.info(f"Chapter {chapter_number} parsed and persisted")

    # Final book is now fully assembled and already saved
    return book
```

---

## Acceptance Criteria

1. `AIProjectGutenbergWorkflow.run()` saves partial `Book` to repository after each chapter completes
2. Repository acts as incremental cache between runs (transparent resume)
3. New parameters: `start_chapter: int = 1`, `end_chapter: Optional[int] = None`
   - `start_chapter`: 1-based chapter index to begin parsing (default: 1)
   - `end_chapter`: 1-based chapter index to end parsing (default: all chapters in book)
   - On restart with `start_chapter=1` and cached partial book exists: auto-resume from last cached chapter
4. Character registry and scene registry are preserved across resume
5. Final `Book` object is identical whether:
   - Run completed in one session, or
   - Run was interrupted and resumed multiple times
6. Cached partial book is loaded and resumed automatically (no explicit `--resume` flag needed)
7. To **clear cache and re-parse from scratch**: specify `--start-chapter 1 --end-chapter N --reparse`
   - `--reparse` flag forces fresh parse (existing flag, works as today)
8. To **parse a subset of chapters**: specify `--start-chapter 10 --end-chapter 20` (useful for testing/debugging)
9. All existing tests pass; no regressions
10. Integration test: Simulate failure at chapter 10, verify resume succeeds and produces identical output
11. Test clearing cache: run with `--reparse`, verify old cache is ignored and fresh parse starts

---

## Out of Scope

- Automatic retry logic on AWS credential expiry (already implemented in US-019 Fix 3)
- Chapter-level caching (only book-level checkpointing)
- Rollback on parse failures (chapters are only saved on successful parse)

---

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/workflows/ai_project_gutenberg_workflow.py` | Add chapter-by-chapter flush logic; add `start_chapter` and `end_chapter` parameters; auto-detect cached partial book and resume |
| `scripts/run_workflow.py` | Add `--start-chapter` and `--end-chapter` CLI flags; respect existing `--reparse` flag for cache-busting |
| `src/workflows/ai_project_gutenberg_workflow_test.py` | New tests for: resume logic, partial book detection, subset parsing, cache clearing |

---

## Implementation Notes

- **Auto-resume behavior**: When `start_chapter=1` (default) and a partial cached book exists:
  - Load cached book from repository
  - Resume from `last_cached_chapter + 1`
  - Transparent to user (no explicit flag needed)
  - Logged: "Resuming from chapter 11 (10 chapters already parsed)"

- **Cache-busting**: Pass `--reparse` flag to ignore cache and re-parse from scratch
  - `--reparse` already exists; leverages existing mechanism

- **Flexible range parsing**: Users can parse any subset:
  - `--start-chapter 10 --end-chapter 20` parses only chapters 10–20
  - Useful for testing, debugging, or re-parsing specific chapters
  - Cache is still respected: if chapters 1–9 exist, they are loaded first

- **Repository must exist** (optional today, required for resume feature)
- **Partial book snapshot is overwritten** on each chapter completion (no need to store all intermediate states)
- **Character registry and scene registry** are threaded through chapters as today; persist with each snapshot
- **No breaking changes**: Existing single-run workflow remains identical
  - Default behavior: `start_chapter=1, end_chapter=None` (all chapters)
  - Auto-resume activates only if cached partial book exists

---

## Success Criteria

Users can:

1. **Auto-resume (default behavior)**:
   ```bash
   make ai CHAPTERS=61
   # Fails at chapter 10
   make ai CHAPTERS=61
   # Auto-resumes from chapter 11 (chapters 1–10 already cached)
   # Logs: "Resuming from chapter 11 (10 chapters already parsed)"
   ```

2. **Clear cache and re-parse**:
   ```bash
   make ai CHAPTERS=61 --reparse
   # Ignores cache, re-parses all 61 chapters from scratch
   ```

3. **Parse subset (testing/debugging)**:
   ```bash
   make ai --start-chapter 5 --end-chapter 15
   # Parses only chapters 5–15
   # Cache for chapters 1–4 is loaded if it exists
   ```

4. **Guaranteed identical output**:
   - Get identical final result whether run in one session or interrupted/resumed multiple times
   - No loss of parsed work
   - Character registry and scene registry preserved across resume

