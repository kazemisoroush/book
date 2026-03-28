# ExecPlan: US-001 Character Registry Enrichment

## Goal

Extend the `Character` model with `sex: str | None` and `age: str | None` fields.
Update the AI section parser to extract these demographics from book text during parsing
and populate the fields in the `CharacterRegistry`.

## User Story

`/workspaces/book/docs/product-specs/us-001-character-enrichment.md`

## Acceptance Criteria (from US-001)

1. `Character` model has `sex: str | None` and `age: str | None` fields (e.g. `"female"`, `"male"`, `"unknown"` for sex; `"young"`, `"adult"`, `"elderly"` for age).
2. The AI parsing step populates these fields for characters it can infer from context.
3. Characters where sex/age cannot be determined have `None` values — no guessing.
4. Narrator character has `sex=None`, `age=None` by default.
5. `Character.to_dict()` and `Character.from_dict()` include the new fields.
6. All existing tests pass. 100% coverage on `domain/`.

## Files To Change

| File | Change |
|---|---|
| `src/domain/models.py` | Add `sex` and `age` fields to `Character`; add `to_dict()` and `from_dict()` methods |
| `src/domain/models_test.py` | Tests for new fields and `to_dict`/`from_dict` |
| `src/parsers/ai_section_parser.py` | Update `_parse_response()` to read `sex`/`age` from AI JSON; update `_build_prompt()` to instruct AI to infer and return these fields |
| `src/parsers/ai_section_parser_test.py` | Tests for `sex`/`age` being parsed and populated on returned characters |

## Implementation Steps (dependency order)

### Step 1 — Extend `Character` model

**What:** Add `sex: Optional[str] = None` and `age: Optional[str] = None` fields to the `Character` dataclass. Add `to_dict()` method that returns a dict with all fields. Add `from_dict()` classmethod that constructs a `Character` from such a dict.

**Layer:** `domain`

**Files:**
- `src/domain/models.py` (source)
- `src/domain/models_test.py` (tests)

**Behaviour:**
- `Character(character_id="harry", name="Harry Potter")` still works (new fields default to `None`)
- `Character(character_id="harry", name="Harry Potter", sex="male", age="young")` works
- `char.to_dict()` returns `{"character_id": "harry", "name": "Harry Potter", "description": None, "is_narrator": False, "sex": "male", "age": "young"}`
- `Character.from_dict({"character_id": "harry", "name": "Harry Potter", "sex": "male", "age": "young"})` returns correct instance
- Narrator from `CharacterRegistry.with_default_narrator()` has `sex=None`, `age=None`
- 100% domain coverage maintained

### Step 2 — Update AI section parser to extract sex/age

**What:** Update `AISectionParser._build_prompt()` to instruct the AI to infer and return `sex` and `age` for each new character. Update `_parse_response()` to read `sex` and `age` from the `new_characters` array in the AI response and pass them to the `Character` constructor.

**Layer:** `parsers` (depends on updated `domain`)

**Files:**
- `src/parsers/ai_section_parser.py` (source)
- `src/parsers/ai_section_parser_test.py` (tests)

**Behaviour:**
- When AI response includes `{"character_id": "hermione", "name": "Hermione Granger", "sex": "female", "age": "young"}` in `new_characters`, the upserted character has `sex="female"` and `age="young"`
- When AI response omits `sex`/`age` from a character, the character has `sex=None`, `age=None`
- When AI response includes `"sex": null`, the character has `sex=None`
- Prompt instructs the AI to infer `sex` (as `"male"`, `"female"`, or `null`) and `age` (as `"young"`, `"adult"`, `"elderly"`, or `null`) for each new character
- Prompt example JSON includes the `sex` and `age` fields in the `new_characters` entry

## Out of Scope

- Voice assignment (US-002)
- Manual override / user-provided character metadata
- Characters introduced after Chapter 1 (parser scope remains the same)

## Pre-existing state

- Baseline: 199 tests pass, ruff clean, mypy clean (as of 2026-03-28)
- `ruff` binary installed via pip (not in PATH at session start)
