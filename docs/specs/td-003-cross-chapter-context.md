# TD-003 — Cross-Chapter Context Windows

**Priority**: Low
**Effort**: Low
**Status**: Open

## Problem

AI context windows are hard-reset at chapter boundaries. If a
conversation or a speaker attribution spans a chapter break, the AI
cannot resolve the speaker correctly in the opening sections of the next
chapter because it has no memory of the preceding chapter's context.

## Impact

- Ambiguous speakers at the start of chapters are more likely to be
  misidentified or labelled `"unknown"`
- Dialogue that resumes mid-scene after a chapter break loses attribution

## What needs doing

- Pass a configurable number of trailing sections from the previous
  chapter as `previous_text` context into the first AI call of the next
  chapter
- Evaluate whether this improves attribution accuracy without
  introducing wrong-chapter speaker confusion

## Risk

More context = higher token cost per call. If the previous chapter ends
with a different scene, injecting it may confuse the AI with irrelevant
speakers. Needs empirical testing.

## Files affected

`src/workflows/ai_project_gutenberg_workflow.py`, `src/parsers/ai_section_parser.py`
