# ExecPlan: OTHER Segment Type (Partial User Story 04)

## Goal

Add a `SegmentType.OTHER` value to handle non-narratable content (page numbers, metadata markers, copyright notices, etc.) that should not be read aloud in the audiobook.

## Source

User story: `docs/product-specs/us-009-junk-section-filtering.md` (partial implementation)

---

## Problem

Project Gutenberg HTML books contain content that should not be narrated:

- Page number artifacts: `{6}`, `{12}`
- In-page copyright notices: `[Copyright 1894 ...]`
- Metadata markers and formatting artifacts

Before this change, such content was classified as `NARRATION` or caused parsing errors. The AI had no way to signal "this should not be read aloud."

---

## Deliverable

### Add `SegmentType.OTHER` to the domain model

The `SegmentType` enum is extended with a new value:

```python
class SegmentType(Enum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    ILLUSTRATION = "illustration"
    COPYRIGHT = "copyright"
    OTHER = "other"  # Non-narratable content
```

The AI section parser prompt is updated to instruct the AI to use `"other"` for non-narratable content like page numbers and metadata markers.

The parser's `_parse_response()` method maps the string `"other"` to `SegmentType.OTHER`.

**Files changed:** `src/domain/models.py`, `src/parsers/ai_section_parser.py`

---

## Acceptance Criteria

1. `SegmentType.OTHER` exists in the enum — [PASS]
2. AI prompt includes instructions to use `"other"` for non-narratable content — [PASS]
3. Parser correctly maps `"other"` responses to `SegmentType.OTHER` — [PASS]
4. `Segment.is_other()` helper method exists — [PASS]
5. All existing tests pass — [PASS]
6. `ruff check src/` and `mypy src/` pass clean — [PASS]

---

## What Was NOT Implemented

User story 04 proposed a comprehensive `SectionFilter` that would:

- Remove page number sections before AI parsing
- Remove copyright sections before AI parsing
- Keep illustration captions and tag them (for future alt-text use)

**Actual implementation**: Instead of pre-filtering, the system relies on the AI to classify junk content as `SegmentType.OTHER`. This is a pragmatic trade-off:

- **Pros**: Leverages AI understanding of content; no need to maintain fragile regex patterns
- **Cons**: Wastes LLM calls on junk sections; no metadata preservation for illustrations

The full `SectionFilter` (deterministic pre-filtering) is deferred to future work.

---

## Impact

Downstream TTS code can now skip segments where `segment.is_other()` returns `True`. The system has a standard way to mark non-narratable content.

In test data, page numbers and copyright notices are correctly classified as OTHER rather than appearing as narration segments.

---

## Out of Scope

- `SectionFilter` class — deferred
- Removing junk sections before AI parsing — deferred
- Preserving illustration captions as metadata — deferred
- Handling all junk patterns deterministically — deferred
