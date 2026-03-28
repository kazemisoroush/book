# ExecPlan: Character Registry (User Story 02)

## Goal

Introduce a proper `CharacterRegistry` data model so that every audio segment
is owned by a named character, the narrator character is never null, and the
registry is threaded through the AI parsing pipeline so characters can be
reused / added across sections.

## Source

User story: `userstories/02_CharacterRegistry.md`

---

## Deliverables

### Step 1 — Add `Character` and `CharacterRegistry` to `domain/models.py`

Add two new dataclasses to the domain layer.

`CharacterRegistry` must have `with_default_narrator()` classmethod,
plus `get()`, `add()`, and `upsert()` methods.

**File changed:** `src/domain/models.py`

---

### Step 2 — Rename `Segment.speaker` to `Segment.character_id`

Change `Segment.speaker: Optional[str]` to `Segment.character_id: Optional[str]`.

**Files changed:** `src/domain/models.py`, `src/domain/models_test.py`,
`src/parsers/ai_section_parser.py`, `src/parsers/ai_section_parser_test.py`,
`src/workflows/ai_project_gutenberg_workflow_test.py`,
`tests/test_ai_workflow_integration.py`

---

### Step 3 — Narration segments receive `character_id = "narrator"`

In `AISectionParser._parse_response()`, narration segments with speaker=null
get `character_id = "narrator"` instead of None.

**File changed:** `src/parsers/ai_section_parser.py`

---

### Step 4 — Thread `CharacterRegistry` through `AISectionParser`

New signature:
  parse(section, registry) -> tuple[list[Segment], CharacterRegistry]

Prompt extended with registry context and reuse instructions.

**Files changed:** `src/parsers/book_section_parser.py`,
`src/parsers/ai_section_parser.py`, `src/parsers/ai_section_parser_test.py`

---

### Step 5 — Add `CharacterRegistry` to `Book` model

`Book.character_registry` field added to store the registry.
`run()` returns `Book` with populated `character_registry`.
Registry threaded through all section parser calls.

**Files changed:** `src/domain/models.py`, `src/workflows/ai_project_gutenberg_workflow.py`,
`src/workflows/ai_project_gutenberg_workflow_test.py`,
`tests/test_ai_workflow_integration.py`

---

## Acceptance Criteria

1. `Character` and `CharacterRegistry` data models exist in `src/domain/models.py`
2. `Segment.character_id: Optional[str]` replaces `Segment.speaker`
3. Narration segments get `character_id = "narrator"` (not null)
4. `AISectionParser.parse()` receives and returns a `CharacterRegistry`
5. AI prompt includes current registry context and reuse instructions
6. `Book.character_registry` field exists; `AIProjectGutenbergWorkflow.run()` returns `Book` with populated registry
7. All existing tests pass; 100% coverage on domain/
8. `ruff check src/` and `mypy src/` pass clean
