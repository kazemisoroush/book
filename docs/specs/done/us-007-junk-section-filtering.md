# US-007: Junk Section Filtering

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
- Copyright notices get classified as `beat_type: copyright` — a made-up
  type not in the domain model.
- Illustration captions get classified as `beat_type: narration`, adding
  noise to the audio output.

Illustration captions are a special case: they carry metadata that may be
useful in the future (e.g. image alt-text, chapter illustrations list) and
should be **preserved** in the parsed output as a distinct type rather than
discarded. They must, however, be skipped by the AI parser to avoid
unnecessary LLM calls.

## Definition: What is a Junk Section?

A section is junk if it contains no prose that should be read aloud. Concrete
patterns found in Project Gutenberg HTML:

1. **Page number artifacts** — text matching `\{\d+\}` (e.g. `{6}`, `{12}`)
2. **In-page copyright blocks** — text matching `\[Copyright.*?\]`
3. **Illustration captions** — short lines (< 60 chars) that are the sole text
   content of a `<div class="figcaption">` or similar figure element, or that
   match the pattern `[A-Z][a-z]+ [&] [A-Z][a-z]+` with no surrounding prose.
   Unlike items 1–2, these are **not discarded** — see Desired State below.

## Desired State

### True junk (page numbers, copyright notices)

The static HTML content parser drops these **before** they are added to
`Chapter.sections`. No such section ever reaches the AI parser.

### Illustration captions

Illustration captions are **kept** in `Chapter.sections` but tagged with a new
`section_type: illustration` value on the `Section` domain model. The AI parser
checks the type before making an LLM call and skips any section whose type is
already resolved (i.e. `illustration`), passing it through unchanged. This
preserves the caption text for future use (e.g. generating alt-text, building
an illustration index) while eliminating the unnecessary LLM call.

A `SectionFilter` is introduced in the `parsers` layer:

```python
class SectionFilter:
    """Classifies and removes non-prose sections.

    - Page number artifacts and copyright blocks are dropped entirely.
    - Illustration captions are kept and tagged with section_type='illustration'.
    """

    def filter(self, sections: list[Section]) -> list[Section]:
        ...
```

The filter is applied inside
`StaticProjectGutenbergHTMLContentParser.parse()` after the section list is
built. It is stateless and deterministic — no AI calls.

## Acceptance Criteria

1. `SectionFilter` exists in `src/parsers/section_filter.py` with unit tests
2. Page number artifacts (`{6}`, `{12}`, etc.) are removed entirely
3. In-page copyright blocks (`[Copyright ...]`) are removed entirely
4. Illustration captions (at minimum the `Mr. & Mrs. Bennet` pattern from the
   Pride and Prejudice fixture) are **kept** and tagged
   `section_type='illustration'`; they are not discarded
5. `Section` domain model gains an `illustration` value in its `section_type`
   enum/literal
6. `StaticProjectGutenbergHTMLContentParser` applies the filter; page number
   and copyright sections from chapter 1 of the Pride and Prejudice fixture do
   not appear in the parsed output; illustration sections do appear with the
   correct type
7. The AI parser skips sections whose `section_type` is `illustration` (no LLM
   call) and passes them through unchanged
8. The AI parser no longer crashes on empty section text
9. All existing tests pass; 100% coverage on `SectionFilter`

## Out of Scope

- Filtering based on AI classification — all filtering is deterministic
- Handling junk sections from non-Gutenberg HTML sources — deferred
- Removing duplicate sections — deferred
- Rendering or using `illustration` sections in audio output — deferred
- Fetching the actual illustration images — deferred
