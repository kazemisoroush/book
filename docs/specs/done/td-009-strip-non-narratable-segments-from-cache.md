# TD-009 — Strip Non-Narratable Segments from Cached Output

## Goal

Remove segments with `character_id: null` from the persisted `book.json`
so the cached output contains only narratable content (dialogue and
narration).

---

## Problem

The cached `book.json` contains segments that will never be spoken aloud.
These segments have `character_id: null` and fall into three categories:

1. **Illustration captions** (`segment_type: "illustration"`) — image
   descriptions embedded in Project Gutenberg HTML (e.g.
   `[Illustration: Mr. Bennet]`).
2. **Copyright notices** (`segment_type: "copyright"`) — legal boilerplate
   at the start or end of the book.
3. **Numbered references / metadata markers** (`segment_type: "other"`) —
   page numbers, footnote markers, and similar non-narrative text.

The TTS orchestrator already skips these at synthesis time (it only
processes `NARRATION` and `DIALOGUE` segments), so they are dead weight
in the cache. They add noise to the JSON, inflate file size, and make
manual inspection harder.

---

## Concept

**Filter before flush**: when the workflow flushes a chapter to the
repository, strip any segment whose `segment_type` is not in
`{NARRATION, DIALOGUE}`.

This is a pure post-processing step on the chapter's sections — no AI,
parser, or domain model changes required.

---

## Where the segments originate

| Source | How | segment_type |
|---|---|---|
| Static content parser labels `section.section_type = "illustration"` | AI parser short-circuits, creates segment without character_id | `illustration` |
| AI response returns `type: "copyright"` | `_parse_response` creates segment with no character_id | `copyright` |
| AI response returns `type: "other"` | `_parse_response` creates segment with no character_id | `other` |

All three paths produce segments where `character_id` is `None` and
`is_narratable` is `False`.

---

## Acceptance criteria

1. After AI segmentation of a chapter, any segment with
   `is_narratable == False` is removed before the chapter is added to the
   book and flushed to the repository.
2. The `book.json` output contains zero segments with
   `character_id: null`.
3. The TTS orchestrator continues to work unchanged (it already filters,
   but now there's nothing to filter).
4. Existing cached books are not migrated — only new parses produce the
   clean output. A `--reparse` re-generates a clean cache.

---

## Out of scope

- Migrating existing cached `book.json` files (use `--reparse` instead).
- Changing the AI prompt or parser to stop producing these segments —
  they are useful during parsing for context, just not in the final
  output.
- Filtering at the `BookSource` level — filtering belongs in the workflow
  after AI segmentation, not in the source.
