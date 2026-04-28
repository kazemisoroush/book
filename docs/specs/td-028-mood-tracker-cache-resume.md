# TD-028 — Mood Tracker & Synthetic-Section Injection Break on Cache Resume

## Problem Statement

A two-chapter `make verify` run against a warm cache (chapter 1 already parsed
and persisted, chapter 2 fresh) produces a book with four correctness defects.
All four share a root cause: workflow state that should be derived from
`book.content.chapters + book.mood_registry` is instead derived from
`ctx.chapters_to_parse`, so resuming mid-book loses state that was established
on earlier runs.

Observed on resume of a 2-chapter run:

- ch1: 40 sections, 28 stamped with `mood_id` — should be 38.
- ch2: 30 sections, 0 stamped with `mood_id` — should be ~30.
- `mood_registry` contains `ch1_mood_1: ch1.3 → ch2.30` — cross-chapter span
  violates the US-034 invariant `start.chapter == end.chapter`.
- ch2 begins with a synthetic `book_title` section (`"Pride and Prejudice,
  by Austen, Jane, 1775-1817."`) that belongs only on ch1.

## Root Cause

Four distinct bugs, each a symptom of the same assumption — "the workflow is
always a fresh run starting at chapter 1":

### Bug 1 — Moods cross chapter boundaries

`src/workflows/mood_tracker.py:47-77` (`MoodTracker.apply`).

`_extend_mood` compares only section-index tuples; it never checks whether
`position.chapter` differs from the currently-open mood's `end.chapter`. When
the parser emits `continue` (or no action, triggering implicit extend) on the
first section of a new chapter while `_open_mood_id` is still set from the
previous chapter, the mood's end silently jumps across the boundary. The
spec invariant from US-034 — "a mood is bounded within a single chapter" —
is violated at runtime with no guard.

On a fresh run this bug is masked: the workflow calls
`mood_tracker.close_chapter(last_position)` at the end of each parsed chapter
(`src/workflows/ai_workflow.py:182-183`), which clears `_open_mood_id`. On a
cache resume, ch1 is never parsed in this process, so `close_chapter` is
never called for it, and the open mood persists into ch2.

### Bug 2 — Back-fill breaks for cross-chapter moods

`src/workflows/mood_tracker.py:235-244` (`_find_covering_mood`).

The function filters `mood.start.chapter != position.chapter`, so a mood with
`start.chapter=1, end.chapter=2` matches neither ch1 positions beyond
`end.section` (because `end.section` is interpreted in ch1's numbering) nor
any ch2 position (start chapter mismatch). That is how ch1 ends up with
28/40 stamped sections and ch2 with 0/30.

This becomes a no-op once Bug 1 is fixed; the defensive filter already
handles the chapter-local case correctly.

### Bug 3 — Cache resume loses tracker state

`src/workflows/ai_workflow.py:118` (construction) and
`src/workflows/mood_tracker.py:37-40` (`__init__`).

`MoodTracker(mood_registry)` starts every run with `_open_mood_id = None`
and `_chapter_mood_count = {}`, ignoring any moods already registered from
cached chapters. On resume, the tracker has no memory that `ch1_mood_1` was
left open at end-of-ch1, and chapter-scoped mood id counters restart from
one, risking collisions (the current registry does upsert-by-id, so a
collision silently overwrites an earlier cached mood).

The LLM prompt continues to show cached moods under "Known moods", so it
reasonably emits `continue` on ch2's first section — but without a seeded
tracker, that `continue` feeds Bug 1.

### Bug 4 — Synthetic `book_title` injected on the first parsed chapter

`src/workflows/ai_workflow.py:233-261` (`_inject_synthetic_sections`).

```python
for i, chapter in enumerate(chapters):
    chapter.sections.insert(0, <chapter_announcement>)
    if i == 0:                       # ← loop index, not chapter number
        chapter.sections.insert(0, <book_title>)
```

On a fresh run `chapters_to_parse == [ch1, ch2, ...]`, so `i == 0` points at
ch1 and the book-title sits in the right place. On a cache resume that
parses `[ch2]`, `i == 0` points at ch2 and the book-title is prepended to
chapter 2, where it doesn't belong. Simultaneously, the cached ch1 still
carries its own book-title from the previous run, so the output now has
two.

## Goal

Restore the invariant that workflow state is derived from
`book.content.chapters + book.mood_registry`, not from `ctx.chapters_to_parse`,
so that a run resuming from cache produces a book byte-equivalent to a fresh
run over the same chapter range.

## Acceptance Criteria

1. **Chapter invariant holds at runtime.**
   `MoodTracker.apply` refuses to extend the currently-open mood when
   `position.chapter != open_mood.end.chapter`. Instead it closes the open
   mood at the last known position of its own chapter, opens a fresh mood in
   the new chapter with `description` carried over, and sets
   `continues_from` on the new mood to the closed mood's id. No registered
   mood ever has `start.chapter != end.chapter`.

2. **Cache resume seeds the tracker.**
   Either `MoodTracker.__init__` rebuilds `_open_mood_id`,
   `_chapter_mood_count`, and `_last_position` from the registry, or the
   workflow passes this context in explicitly. After construction, the
   tracker's state must match what it would be after a fresh run that
   parsed the cached chapters in order and called `close_chapter` at each
   boundary.

3. **Synthetic book-title is chapter-1-only.**
   `_inject_synthetic_sections` prepends the synthetic `book_title` section
   iff `chapter.number == 1`, never based on loop index. On a cache resume
   where ch1 is not in `chapters_to_parse`, no chapter receives a new
   book-title section.

4. **Back-fill stamps every section in the parsed range.**
   After `MoodTracker.finalize`, every `Section` in every chapter of
   `book.content.chapters` has `mood_id` set, provided at least one mood
   was registered. (A section may still have `mood_id = None` if the entire
   book registered zero moods — a fake-parser scenario.)

5. **`_find_covering_mood` needs no change beyond what falls out of Bug 1.**
   The function already filters to chapter-local moods correctly. The spec
   may note that this function's correctness depends on Bug 1's fix.

6. **New tests.**
   - `src/workflows/mood_tracker_test.py`:
     - Construct a tracker from a non-empty registry whose last mood ends
       in ch1; assert `open_mood_id` is that mood and `_chapter_mood_count`
       reflects ch1's count. Close-chapter was implicitly called (because
       the end-of-ch1 section is past the tracker's expected "cursor").
     - Construct a tracker from a registry whose last mood ends earlier
       than the last section in its chapter; assert tracker is still
       "open" on that mood.
     - Apply `continue` with a position in a different chapter than the
       open mood; assert the old mood was closed at its chapter's last
       seen section and a new mood was opened with `continues_from` set.
   - `src/workflows/ai_workflow_test.py`:
     - Cache hit on ch1, fresh parse of ch2. Assert ch2's first section is
       the synthetic `chapter_announcement` (not `book_title`), ch1's
       section count is unchanged from the cached run, ch1 sections all
       have `mood_id`, and ch2 sections all have `mood_id`.
     - Assert no mood in the registry has `start.chapter != end.chapter`.

7. **Evals.**
   The US-034 mood-change evals under `src/evals/` continue to pass.
   Add one eval case (or promptfoo fixture) that exercises a two-chapter
   resume and asserts the chapter-boundary behaviour.

8. **`make verify` on the 2-chapter Pride and Prejudice fixture** produces
   a book whose `output.json` has:
   - ch1 and ch2 both fully stamped with `mood_id`,
   - no synthetic `book_title` on ch2,
   - every registered mood chapter-local,
   - cross-chapter arcs (if any) expressed via `continues_from`, not by
     extending `end` across the boundary.

9. `pytest -v`, `ruff check src/`, and `mypy src/` pass.

## Out of Scope

- Reworking how `chapters_to_parse` is computed in `ProjectGutenbergBookSource`
  — the set of cached-vs-to-parse chapters is already correct; only the
  downstream consumers mishandle it.
- Rewriting the mood prompt. The LLM contract from US-034 is unchanged.
- Adding a runtime check that book-title sections are unique in the book
  (could be a separate hardening step; noted as a candidate for a follow-up
  td spec).
- Touching the merge pass (`_merge_short_moods`). Chapter-local behaviour
  is already correct there, modulo Bug 1's effects.

## Key Design Decisions

### Seed the tracker from the registry, don't plumb `chapters_to_parse`

`MoodTracker` already receives the registry. Reconstructing its state from
the registry keeps the public surface small and avoids teaching the tracker
about resume concepts. The reconstruction rule:

- Group moods by `start.chapter`; `_chapter_mood_count[c]` = count of moods
  whose `start.chapter == c`.
- The "candidate open mood" is the mood with the largest
  `(end.chapter, end.section)` key.
- If `candidate.end.chapter < first_chapter_to_parse`, treat the candidate
  as closed (`_open_mood_id = None`). The workflow's prior
  `close_chapter(last_position)` call already ran.
- Otherwise set `_open_mood_id = candidate.mood_id`.

The workflow passes `first_chapter_to_parse` into `MoodTracker` construction,
derived from `ctx.chapters_to_parse[0].number` when non-empty, else
`ctx.content.chapters[0].number` as a safe default.

### Auto-close on chapter transition

Rather than duplicate the close logic between `close_chapter` and `apply`,
`apply` detects the chapter transition and delegates to the existing
close/open primitives. The new mood receives `description = old.description`
by default, overridden by the action if the action itself supplies one
(only `open` and `close_and_open` do; `continue` does not, so the
description is carried).

### Book-title guard on `chapter.number`, not loop index

The synthetic-section injector is a pure function of the chapter's identity.
Using `chapter.number == 1` makes the injector resume-safe and removes the
need for `enumerate`. Collapse back to `for chapter in chapters:`.

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/workflows/mood_tracker.py` | Seed state from registry in `__init__`; detect chapter transition in `apply`; auto-close + open-with-`continues_from`; track `_last_position` per chapter |
| `src/workflows/ai_workflow.py` | Pass `first_chapter_to_parse` to `MoodTracker`; change synthetic-injector guard to `chapter.number == 1`; collapse `enumerate` |
| `src/workflows/mood_tracker_test.py` | Add resume-seeding + chapter-transition tests |
| `src/workflows/ai_workflow_test.py` | Add 2-chapter cache-resume correctness test |
| `src/evals/` (mood-change eval suite) | Extend with one 2-chapter resume case |

## Implementation Notes

- TDD: write the failing tests first. The simplest red test is the
  constructor-from-registry one — it fails immediately against the current
  `__init__`.
- Preserve the existing `close_chapter` public method; new logic in `apply`
  should call it (or a shared internal helper) rather than duplicating the
  registry mutation.
- After fixing Bug 1, re-run the previously-captured 2-chapter
  `output.json` and diff against a fresh-run `output.json`; they should be
  byte-equivalent except for AI call counts / non-deterministic metadata.
- No backwards compatibility shims. The cached `book.json` format is
  unchanged (the bug is in transient runtime state, not persisted schema).
