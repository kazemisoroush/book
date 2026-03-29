# TD-006 — EPUB and PDF Support

**Priority**: Low
**Effort**: High
**Status**: Open

## Problem

The pipeline only ingests Project Gutenberg HTML zips. EPUB and PDF are
the dominant book formats in the wild and are not supported at all.

## Impact

- Cannot process any book outside Project Gutenberg
- Limits the project to public domain works with Gutenberg URLs

## What needs doing

- Implement an EPUB parser: extract chapter structure, text, and inline
  emphasis (EPUB is ZIP-of-XHTML; structure maps well to current domain
  model)
- Implement a PDF text extractor: harder — PDFs have no semantic
  structure, so chapter detection needs heuristics
- Abstract the downloader interface so non-URL sources (local files) are
  supported
- Add a new workflow (or extend existing) for non-Gutenberg input

## Priority order

EPUB first — it has semantic structure and maps cleanly to the existing
`Book` / `Chapter` / `Section` model. PDF is much harder and likely
lower value.

## Files affected

New `src/parsers/epub_content_parser.py`,
new `src/parsers/epub_metadata_parser.py`,
new `src/workflows/epub_workflow.py`,
`src/workflows/__init__.py`
