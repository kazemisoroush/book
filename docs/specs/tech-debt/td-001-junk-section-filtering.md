# TD-001 — Junk Section Filtering

**Priority**: High
**Effort**: Medium
**Status**: Open

## Problem

Junk sections — page numbers, copyright notices, illustration captions
— are still forwarded to the AI segmentation step. `SegmentType.OTHER`
exists in the domain model but the `SectionFilter` wiring into the
content parser is incomplete. Every junk section burns an LLM call and
inflates Bedrock costs.

## Impact

- Higher API costs per chapter
- Slower parsing (every junk section round-trips to Bedrock)
- Illustration metadata not preserved for downstream use

## What needs doing

- Implement `SectionFilter` in `src/parsers/section_filter.py` (stub
  already exists)
- Wire it into `StaticProjectGutenbergHtmlContentParser` so junk
  sections are classified before reaching `AISectionParser`
- Mark illustration sections as `section_type="illustration"` so the AI
  short-circuit in `AISectionParser` skips the LLM call

## Files affected

`src/parsers/section_filter.py`, `src/parsers/static_project_gutenberg_html_content_parser.py`

## Related

US-007 spec (archived) describes the full acceptance criteria.
