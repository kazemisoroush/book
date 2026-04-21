# TD-026 — Rename Segment to Beat

## Problem

"Section" and "segment" are too similar — easy to confuse in code and
conversation. A section is the output of deterministic book parsing. A segment
is the output of AI parsing a section into units of speech with consistent tone
and expression. The names don't convey this distinction.

## Proposed Solution

Rename `Segment` to `Beat` everywhere in the codebase. A beat is the smallest
unit of dramatic action where one character's emotion and expression hold — a
term borrowed from screenwriting. A section contains one or more beats,
depending on character feelings, speaker changes, and expressive shifts.

`SegmentType` becomes `BeatType`. All field names, method names, log keys, and
JSON serialisation keys change from `segment` to `beat`.
