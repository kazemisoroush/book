# US-005: Trim Output to AI-Processed Chapters

## Goal

When `chapter_limit` is set, the output JSON contains all chapters from the
book — including unprocessed ones with empty segments. This is misleading.
The output should only include chapters that were actually AI-processed.

## Acceptance Criteria

1. When `chapter_limit=N` is set, `Book.content.chapters` in the output
   contains exactly N chapters (the processed ones), not the full book.
2. When `chapter_limit` is not set (full book), all chapters are included
   as before.
3. `AIProjectGutenbergWorkflow` is responsible for trimming — the `Book`
   object it returns only contains the processed chapters.
4. All existing tests pass. `ruff` and `mypy` clean.

## Out of Scope

- Partial section processing within a chapter
- Resuming or checkpointing a partial run
