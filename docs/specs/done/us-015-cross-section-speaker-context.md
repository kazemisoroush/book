# US-015 — Cross-Section Speaker Context

## Goal

Pass a rolling window of surrounding section texts to the AI beater so
that short one-line exchanges (e.g. `"Bingley."`, `"Is he married or
single?"`) are attributed to the correct speaker rather than defaulting to
the last character mentioned.

---

## Background / motivation

The AI section parser processes each paragraph in isolation. In tight
back-and-forth dialogue, a one-line paragraph like `"Bingley."` has no
internal cue indicating the speaker — the model must infer it from
surrounding context. Without that context it frequently defaults to the
most recently mentioned character, producing attribution runs where a
single character appears to speak several consecutive lines when in fact
two characters are alternating.

Example from Chapter I of Pride and Prejudice (incorrectly attributed):

```
"What is his name?"          → mrs_bennet  ✗ (should be mr_bennet)
"Bingley."                   → mrs_bennet  ✓
"Is he married or single?"   → mrs_bennet  ✗ (should be mr_bennet)
"Oh, single, my dear…"       → mrs_bennet  ✓
```

The fix is to provide the N sections immediately preceding (and optionally
following) the current section as a read-only context block in the prompt.
The model already knows how to use context — it just isn't being given any.

---

## Acceptance criteria

1. `AISectionParser` accepts a `context_window: int = 3` parameter (number
   of preceding section texts to include in the prompt).

2. When beating section `i`, the prompt includes the plain text of
   sections `i-k … i-1` (up to `context_window` items, fewer if near the
   start of a chapter) under a clearly labelled `"preceding context"` block.
   The model is instructed that this context is **read-only** — it must not
   produce beats for those sections.

3. The character registry accumulated so far is still forwarded (existing
   behaviour). The context window adds text only, not beat data.

4. No new AI calls are made for the context sections — the window is
   constructed from already-parsed plain text.

5. `make verify` (3 chapters) produces correct speaker attribution for the
   Bennet dialogue in Chapter I: `"What is his name?"` and `"Is he married
   or single?"` are attributed to `mr_bennet`.

6. Unit tests cover:
   - Context window is included in the prompt string when previous sections exist.
   - Context window is absent (or empty) when the section is the first in a chapter.
   - Window is capped at `context_window` items (does not include sections
     from earlier than `i - context_window`).

---

## Out of scope

- Forward context (sections after `i`) — preceding context is sufficient
  for speaker inference and avoids lookahead complexity.
- Persisting context across chapter boundaries.
- Changing the beat output schema.

---

## Key design decisions

### Read-only context, not re-beatation
The context block is labelled explicitly in the prompt so the model knows
it must not produce output for those lines. This avoids double-processing
and keeps token cost low (context is plain text, not full beat JSON).

### Default window of 3
Three preceding paragraphs covers the typical alternating-dialogue pattern
in literary fiction without inflating token usage significantly. The
parameter is tunable per call site if needed.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/parsers/ai_section_parser.py` | Accept + thread `context_window`; build context block; update prompt |
| `src/parsers/ai_section_parser_test.py` | Tests for context inclusion/exclusion/capping |
| `src/workflows/ai_project_gutenberg_workflow.py` | Pass preceding section texts when calling the parser |
