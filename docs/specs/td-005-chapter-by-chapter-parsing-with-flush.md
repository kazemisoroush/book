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
# Pseudo-code for the new workflow

for chapter_number in range(1, total_chapters + 1):
    # Parse chapter
    parsed_chapter = parse_chapter(chapter_number)

    # Add to in-memory book
    book.content.chapters.append(parsed_chapter)

    # Flush to repository immediately
    if repository is not None:
        repository.save(book, book_id)  # Overwrites previous snapshot

    logger.info(f"Chapter {chapter_number} parsed and persisted")

# Final book is now fully assembled and already saved
return book
```

---

## Acceptance Criteria

1. `AIProjectGutenbergWorkflow.run()` saves partial `Book` to repository after each chapter completes
2. On restart (same `book_id`, `reparse=False`), detect partial book in repository
3. Resume from chapter (last_completed_chapter + 1) instead of restarting from chapter 1
4. Character registry and scene registry are preserved across resume
5. Final `Book` object is identical whether:
   - Run completed in one session, or
   - Run was interrupted and resumed multiple times
6. New parameter: `start_from_chapter: int = 1` (defaults to 1; set to N+1 on resume)
7. CLI: New `--resume` flag automatically detects and resumes from last saved chapter
8. All existing tests pass; no regressions
9. Integration test: Simulate failure at chapter 10, verify resume succeeds and produces identical output

---

## Out of Scope

- Automatic retry logic on AWS credential expiry (already implemented in US-019 Fix 3)
- Chapter-level caching (only book-level checkpointing)
- Rollback on parse failures (chapters are only saved on successful parse)

---

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/workflows/ai_project_gutenberg_workflow.py` | Add chapter-by-chapter flush logic; add `start_from_chapter` parameter |
| `scripts/run_workflow.py` | Add `--resume` flag to auto-detect and resume from last chapter |
| `src/workflows/ai_project_gutenberg_workflow_test.py` | New tests for resume logic and partial book detection |

---

## Implementation Notes

- `start_from_chapter` defaults to 1; on resume, set it to (last_saved_chapter + 1)
- Repository must exist (optional today, required for resume)
- Partial book snapshot is overwritten on each chapter completion (no need to store all intermediate states)
- Character registry and scene registry are threaded through chapters as today; persist with each snapshot
- No breaking changes: existing single-run workflow remains identical

---

## Success Criteria

Users can:
1. Run `make ai CHAPTERS=61 --resume` and if it fails at chapter 10, run it again and resume from chapter 11
2. See log output: "Resuming from chapter 11 (9 chapters already parsed)"
3. Get identical final output regardless of interruptions/resume count
4. Not lose any parsed work

