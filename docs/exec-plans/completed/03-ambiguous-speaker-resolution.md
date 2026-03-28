# ExecPlan: Ambiguous Speaker Resolution (User Story 03)

## Goal

Enable the AI section parser to resolve ambiguous speakers by providing surrounding sections as read-only context. This allows the AI to follow conversational turn-taking, resolve pronouns, and infer speakers from narrative flow.

## Source

User story: `docs/product-specs/us-008-ambiguous-speaker-resolution.md`

---

## Problem

Many dialogue segments came back with `character_id: null` because the AI could not identify the speaker from the section text alone. For example, in chapter 1 of *Pride and Prejudice*, Mr. Bennet's dialogue segments had no speaker because quotes like:

```
"You want to tell me, and I have no objection to hearing it."
```

contain no attribution text. A human reader knows from the flow of conversation that this is Mr. Bennet replying to Mrs. Bennet, but an AI parsing this section in isolation cannot determine the speaker.

---

## Deliverables

### Step 1 — Add `context_window` parameter to `BookSectionParser.parse()`

The abstract base class signature is updated to accept an optional context window:

```python
def parse(
    self,
    section: Section,
    registry: CharacterRegistry,
    context_window: Optional[list[Section]] = None,
) -> tuple[list[Segment], CharacterRegistry]:
    ...
```

**File changed:** `src/parsers/book_section_parser.py`

---

### Step 2 — Extend `AISectionParser` prompt to include context

When `context_window` is provided, the prompt includes a "surrounding context" block showing the text of the neighbouring sections (without asking the AI to re-segment them).

The prompt explicitly instructs the AI to use the context for speaker inference only.

**File changed:** `src/parsers/ai_section_parser.py`

---

### Step 3 — Thread context window through `AIProjectGutenbergWorkflow`

For each section in each chapter, the workflow builds a context window containing the 3 preceding sections from the same chapter (or fewer if at the start of a chapter).

Context windows never cross chapter boundaries.

```python
_CONTEXT_WINDOW_SIZE = 3

for chapter in chapters_to_segment:
    for idx, section in enumerate(chapter.sections):
        start = max(0, idx - _CONTEXT_WINDOW_SIZE)
        context_window = chapter.sections[start:idx]
        section.segments, registry = self.section_parser.parse(
            section, registry, context_window=context_window
        )
```

**File changed:** `src/workflows/ai_project_gutenberg_workflow.py`

---

## Acceptance Criteria

1. `BookSectionParser.parse()` signature includes optional `context_window` parameter — [PASS]
2. `AISectionParser.parse()` accepts the context window — [PASS]
3. When provided, the context window appears in the AI prompt as read-only surrounding context — [PASS]
4. `AIProjectGutenbergWorkflow` passes the 3 preceding sections as context for each section — [PASS]
5. Context windows do not cross chapter boundaries — [PASS]
6. All existing tests pass — [PASS]
7. `ruff check src/` and `mypy src/` pass clean — [PASS]

---

## Impact

After implementation, the rate of `character_id: null` dialogue segments dropped significantly. In the Pride and Prejudice chapter 1 test case, Mr. Bennet's dialogue segments are now correctly attributed with his character ID in the registry.

The AI can now follow conversational turn-taking across section boundaries and resolve pronouns like "he" and "she" to registry entries based on the narrative flow in the context window.

---

## Out of Scope

- Cross-chapter context windows — deferred
- Retroactively re-resolving already-parsed sections — deferred
- Merging duplicate registry entries — deferred
- Configurable context window size (hardcoded to 3) — deferred
