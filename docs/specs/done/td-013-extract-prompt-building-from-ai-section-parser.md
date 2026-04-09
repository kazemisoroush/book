# TD-013 — Extract Prompt Building from AISectionParser

## Goal

Remove `book_title`/`book_author` context from the `AISectionParser`
constructor and prompt building. This context belongs in the AI provider
or a dedicated prompt builder, not in the parser.

---

## Problem

`AISectionParser` (`src/parsers/ai_section_parser.py:186-188`) accepts
`book_title` and `book_author` in its constructor and threads them into
`_build_prompt`. This is a **leaking abstraction** — the parser is
assembling AI prompt context that belongs at a different layer.

---

## Concept

Either:
- Pass book context via the `Section` model (it already carries chapter
  metadata), or
- Extract prompt assembly into a dedicated `PromptBuilder` class that the
  workflow composes with the parser.

The parser should receive a ready-to-use prompt or the minimal data it needs
to parse — not raw book metadata.

---

## Acceptance criteria

1. `AISectionParser` no longer accepts `book_title`/`book_author` in its
   constructor.
2. Prompt context is assembled by a dedicated builder or passed through
   the domain model.
3. All existing tests continue to pass.
4. No change in AI output quality — the same context reaches the prompt.

---

## Out of scope

- Changing the AI prompt content or improving prompt quality.
- Refactoring other parsers.
