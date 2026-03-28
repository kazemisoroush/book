# ExecPlan Guide

## What is an ExecPlan?

An ExecPlan is a structured specification for implementing a feature or refactor. It breaks complex work into testable steps with explicit acceptance criteria.

ExecPlans are used by the Orchestrator agent to drive the TDD loop. The Orchestrator reads the ExecPlan, dispatches Test Agent and Coder Agent for each step, and verifies that all acceptance criteria pass before handing off to Doc Updater.

## When to Create an ExecPlan

Use an ExecPlan when the work:

- Spans more than two modules
- Requires research or design decisions before implementation
- Involves external APIs or third-party integrations
- Could take more than one agent session to complete
- Has complex acceptance criteria that need to be verified systematically

**Don't use an ExecPlan for**:

- Single-file bug fixes
- Simple refactors (rename, extract method)
- Documentation-only changes
- Tasks with obvious implementation (no design decisions)

For simple tasks, give the Orchestrator a plain description and let it work ad-hoc.

## ExecPlan Lifecycle

```
User creates ExecPlan
  → save to docs/exec-plans/active/<name>.md
  ↓
Orchestrator reads ExecPlan
  → executes steps (Test Agent + Coder Agent loop)
  → verifies acceptance criteria
  → hands off to Doc Updater
  ↓
Orchestrator emits Completion Report
  ↓
Human reviews and approves
  ↓
Human moves ExecPlan to docs/exec-plans/completed/<name>.md
```

ExecPlans are **never modified** during execution. If a step proves infeasible or a criterion cannot be met, the Orchestrator stops and asks the human for guidance.

## ExecPlan Template

```markdown
# ExecPlan: <Feature Name> (User Story <number>)

## Goal

<One-paragraph description of what this ExecPlan delivers and why.>

## Source

User story: `userstories/<number>_<name>.md`
OR
Ad-hoc task requested by: <person/context>

---

## Deliverables

### Step 1 — <What gets done>

<Description of this step. What files are created or modified? What behavior changes?>

**Files changed:** `path/to/file.py`, `path/to/other_file.py`

---

### Step 2 — <Next step>

<Description>

**Files changed:** `path/to/file.py`

---

(Repeat for all steps)

---

## Acceptance Criteria

1. <Criterion> — testable condition that must be true
2. <Criterion>
3. All existing tests pass
4. `ruff check src/` and `mypy src/` pass clean
5. 100% coverage on domain/ (if domain models changed)

---

## Out of Scope

- <Feature explicitly deferred>
- <Edge case not handled>
- <Future work noted during planning>
```

## Writing Good Acceptance Criteria

Acceptance criteria must be:

1. **Testable** — you can write a test that proves it's true
2. **Unambiguous** — no room for interpretation
3. **Verifiable** — the Orchestrator can check it mechanically

**Good criteria**:

- `Character` and `CharacterRegistry` data models exist in `src/domain/models.py`
- `Segment.character_id: Optional[str]` replaces `Segment.speaker`
- `AISectionParser.parse()` accepts `context_window: Optional[list[Section]]`
- All tests in `src/parsers/ai_section_parser_test.py` pass

**Bad criteria** (too vague):

- Parser works better
- Code is more maintainable
- AI understands context
- Users are happier

If a criterion cannot be turned into a test, it's not a criterion — it's a hope.

## Referencing Source Files

If the ExecPlan implements a user story, reference it:

```markdown
## Source

User story: `userstories/03_AmbiguousSpeakerResolution.md`
```

If it's ad-hoc:

```markdown
## Source

Ad-hoc task: Fix null narrator bug found in production logs.
```

## Files Changed

Each step lists the files it touches. This helps the Orchestrator understand dependencies and dispatch work in the right order.

If step 2 depends on types created in step 1, the Orchestrator knows not to start step 2 until step 1 is complete.

## Out of Scope

Explicitly list what this ExecPlan does NOT do. This prevents scope creep and sets clear expectations.

Good things to note:

- Features deferred to future work
- Edge cases not handled
- Design decisions made (and alternatives rejected)
- Performance optimizations skipped

## Completion

When the Orchestrator declares the ExecPlan complete:

1. Review the Completion Report
2. Run `make test` and `make lint` yourself
3. Spot-check the implementation against acceptance criteria
4. If satisfied, move the ExecPlan to `docs/exec-plans/completed/`
5. Optionally open a PR (or commit directly if you're the owner)

The ExecPlan is a **historical record** of what was implemented and why. Never delete completed ExecPlans — they're part of the project's memory.
