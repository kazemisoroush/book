# US-001: Character Registry Enrichment

## Goal

During AI parsing, extract `sex` and `age` for each character from the book text and store them in `CharacterRegistry`. This enables downstream voice assignment to match character voices to character demographics.

## Acceptance Criteria

1. `Character` model has `sex: str | None` and `age: str | None` fields (e.g. `"female"`, `"male"`, `"unknown"` for sex; `"young"`, `"adult"`, `"elderly"` for age).
2. The AI parsing step populates these fields for characters it can infer from context.
3. Characters where sex/age cannot be determined have `None` values — no guessing.
4. Narrator character has `sex=None`, `age=None` by default.
5. `Character.to_dict()` and `Character.from_dict()` include the new fields.
6. All existing tests pass. 100% coverage on `domain/`.

## Out of Scope

- Voice assignment (that is US-002)
- Manual override / user-provided character metadata
- Characters introduced after Chapter 1
