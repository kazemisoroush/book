# US-006: Refactor Book Parser Layer

## Goal

Refactor the book parser layer for better maintainability, extensibility, automated
testability, and generalisability (the same code should work for all books, not just
one specific title).

The parser layer converts raw text books into the `Book` data model, then uses AI
LLMs to break sections into fine-grained segments and add context for a better
audio experience.

## Background

The `Book` data model captures title, author, chapters, sections, and segments. A
segment is the smallest unit — a single dialogue line or a narration run — and
carries speaker attribution so the TTS layer can assign distinct voices.

Example section containing mixed dialogue and narration:

```
"I'm a what?" gasped Harry. "A wizard, o' course," said Hagrid, sitting back down
on the sofa.
```

Desired segments:

1. Dialogue — "I'm a what?" (speaker: Harry Potter)
2. Narration — "gasped Harry."
3. Dialogue — "A wizard, o' course," (speaker: Rubeus Hagrid)
4. Narration — "said Hagrid, sitting back down on the sofa."

## Problem Areas

### Segment Recognition

The current parser uses regex-based pattern matching (`ATTRIBUTION_PATTERNS`) to
detect dialogue and narration. Limitations:

- Struggles with nested quotes or unusual punctuation
- Does not handle interrupted dialogue
- Requires manual pattern maintenance for edge cases
- Not generalisable across books with different writing styles

### Character Recognition

The current parser uses deterministic patterns to identify speakers. This fails with:

- Implicit attribution ("He nodded" without naming who "he" is)
- Characters referred to by different names or pronouns
- Complex multi-exchange dialogue

## Desired State

### Segment Recognition

Use AI LLMs to segment text into dialogue and narration:

- Send section text to the LLM with book and character context
- LLM returns structured segments: type (dialogue / narration), text, and speaker
  for dialogue lines
- AI handles interrupted dialogue, nested quotes, implied speakers, and unusual
  formatting
- Generalisable across books and writing styles

### Character Recognition and Registry

Use AI LLMs to maintain the `CharacterRegistry`:

- LLM analyses dialogue segments with book context
- Identifies speakers by name, even from implicit references
- Builds and updates the registry with: character name, aliases, context, voice
  narrator reference
- Each LLM request receives the current registry; the LLM returns the updated
  registry with newly discovered characters or aliases

## Book Information Recognition

Title, author, chapters, and sections are determined heuristically from the raw text.
This approach is adequate for the current scope and will be revisited if needed.

## Rules

1. TDD — write failing tests before implementation
2. SOLID — single responsibility, open/closed, etc.
3. Do not be afraid to remove files and start over when needed
4. All tests pass locally
5. All linter rules pass locally

## Out of Scope

- Changing the heuristic approach to book information recognition (title, author,
  chapters)
- Support for non-Gutenberg book formats
