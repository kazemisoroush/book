# TD-026 — Rename Beat to Beat

## Problem

"Section" and "beat" are too similar — easy to confuse in code and
conversation. A section is the output of deterministic book parsing. A beat
is the output of AI parsing a section into units of speech with consistent tone
and expression. The names don't convey this distinction.

## Proposed Solution

Rename `Beat` to `Beat` everywhere in the codebase. A beat is the smallest
unit of dramatic action where one character's emotion and expression hold — a
term borrowed from screenwriting. A section contains one or more beats,
depending on character feelings, speaker changes, and expressive shifts.

`BeatType` becomes `BeatType`. All field names, method names, log keys, and
JSON serialisation keys change from `beat` to `beat`.
