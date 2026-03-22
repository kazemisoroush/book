# User Story 04 — Junk Section Filtering

## Problem Statement

The static HTML content parser produces sections that are not book content.
Running the AI pipeline on chapter 1 of *Pride and Prejudice* reveals three
categories of junk sections leaking through:

| Example text | Type |
|---|---|
| `{6}` | Page number artifact |
| `[Copyright 1894 by George Allen. ]` | In-page copyright notice |
| `Mr. & Mrs. Bennet` | Illustration caption |

These sections reach the AI parser and cause problems:
- Page number artifacts (`{6}`) return an empty AI response, crashing the
  parser with a JSON parse error.
- Copyright notices get classified as `segment_type: copyright` — a made-up
  type not in the domain model.
- Illustration captions get classified as `segment_type: narration`, adding
  noise to the audio output.

---

## Definition: What is a Junk Section?

A section is junk if it contains no prose that should be read aloud. Concrete
patterns found in Project Gutenberg HTML:

1. **Page number artifacts** — text matching `\{\d+\}` (e.g. `{6}`, `{12}`)
2. **In-page copyright blocks** — text matching `\[Copyright.*?\]`
3. **Illustration captions** — short lines (< 60 chars) that are the sole text
   content of a `<div class="figcaption">` or similar figure element, or that
   match the pattern `[A-Z][a-z]+ [&] [A-Z][a-z]+` with no surrounding prose

---

## Desired State

The static HTML content parser filters junk sections **before** they are added
to the `Chapter.sections` list. No junk section ever reaches the AI parser.

A `SectionFilter` is introduced in the `parsers` layer:

```python
class SectionFilter:
    """Removes non-prose sections from a chapter's section list."""

    def filter(self, sections: list[Section]) -> list[Section]:
        ...
```

The filter is applied inside
`StaticProjectGutenbergHTMLContentParser.parse()` after the section list is
built. It is stateless and deterministic — no AI calls.

---

## Acceptance Criteria

1. `SectionFilter` exists in `src/parsers/section_filter.py` with unit tests
2. Page number artifacts (`{6}`, `{12}`, etc.) are removed
3. In-page copyright blocks (`[Copyright ...]`) are removed
4. Illustration captions are removed (at minimum the `Mr. & Mrs. Bennet`
   pattern from the Pride and Prejudice fixture)
5. `StaticProjectGutenbergHTMLContentParser` applies the filter; the 3 junk
   sections in chapter 1 of the Pride and Prejudice fixture do not appear in
   the parsed output
6. The AI parser no longer crashes on empty section text
7. All existing tests pass; 100% coverage on `SectionFilter`

---

## Out of Scope

- Filtering based on AI classification — all filtering is deterministic
- Handling junk sections from non-Gutenberg HTML sources — deferred
- Removing duplicate sections — deferred
