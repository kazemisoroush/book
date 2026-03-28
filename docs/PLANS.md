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

User story: `docs/product-specs/us-<NNN>-<slug>.md`
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

## Completion

When the Orchestrator declares the ExecPlan complete, move it to `docs/exec-plans/completed/`. Completed ExecPlans are historical records — never delete them.
