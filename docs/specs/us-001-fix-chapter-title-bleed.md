# US-004: Fix Chapter Title Bleed in Static Content Parser

## Goal

The static HTML content parser incorrectly includes the last sentence of the
previous chapter in the following chapter's title. For example:

```
Chapter 2: 'I hope Mr. Bingley will like it.CHAPTER II.'
Chapter 3: 'He rode a black horse.CHAPTER III.'
```

Chapter titles should contain only the chapter heading text.

## Acceptance Criteria

1. `StaticProjectGutenbergHTMLContentParser` produces chapter titles that
   contain only the heading text (e.g. `"Chapter II."`), with no trailing
   content from the preceding chapter.
2. Tested against Pride and Prejudice (book ID 1342) — all chapter titles
   match the pattern `Chapter <Roman numeral>.` or equivalent heading text.
3. All existing tests pass. `ruff` and `mypy` clean.

## Out of Scope

- Other book formats or non-Gutenberg HTML structures
- Section title parsing (chapters only)
