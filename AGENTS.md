# Audiobook Generator — Agent Guide

## What this is
A Python CLI that converts plain-text books (Project Gutenberg format) into
multi-voice audiobooks using ElevenLabs TTS. Characters are detected
automatically and assigned distinct voices. Output is a single assembled
audio file per book.

## Read first
- [CLAUDE.md](CLAUDE.md) — project conventions, non-negotiables, layer rules
- [ARCHITECTURE.md](ARCHITECTURE.md) — domain map, layer model, dependency rules

## Agent fleet

Agent definitions live in [.claude/agents/](.claude/agents/). Each file is a
self-contained system prompt loaded by Claude Code.

| Agent | File | Role |
|---|---|---|
| Orchestrator | `.claude/agents/orchestrator.md` | Owns a task end-to-end |
| Test Agent | `.claude/agents/test-agent.md` | Writes failing tests only |
| Coder Agent | `.claude/agents/coder-agent.md` | Writes minimum implementation |
| Doc Updater | `.claude/agents/doc-updater.md` | Fixes doc/code drift |
| Test Auditor | `.claude/agents/test-auditor.md` | Removes low-value tests, enforces AAA |

## Working model
**Humans steer. Agents execute.**

```
Human gives task (ExecPlan path or description)
   │
   ▼
Orchestrator
   │  reads ExecPlan, decomposes into steps
   │
   ├─► for each step ──────────────────────────────────────┐
   │                                                        │
   │   Test Agent                                           │
   │   └─ writes failing *_test.py                         │
   │   └─ confirms pytest FAILS                            │
   │   └─ reports test file + what each test asserts       │
   │       │                                               │
   │       ▼                                               │
   │   Coder Agent                                         │
   │   └─ reads tests, writes minimum implementation       │
   │   └─ runs: pytest + ruff + mypy                      │
   │   └─ reports PASS or FAIL                            │
   │       │                                               │
   │       ├─ FAIL ──► Coder Agent retries (up to 5x)     │
   │       │                                               │
   │       └─ PASS ──► next step ──────────────────────────┘
   │
   │  (all steps complete)
   │
   ▼
Orchestrator verifies
   └─ re-reads all changed files
   └─ checks each ExecPlan acceptance criterion [PASS/FAIL]
   └─ runs full check suite
   └─ if any gap: re-enters TDD loop for that gap
   │
   ▼
Doc Updater
   └─ receives list of changed files
   └─ finds drift between code and docs
   └─ makes minimal edits
   └─ reports what changed
   │
   ▼
Orchestrator emits Completion Report
   └─ human reviews and decides whether to open PR
```

### Agent responsibilities (one-line each)

- **Orchestrator** — decomposes work, drives the loop, verifies against the plan, hands off to Doc Updater.
- **Test Agent** — writes failing tests that precisely specify behaviour; never touches implementation.
- **Coder Agent** — writes the minimum code to make tests pass; never modifies tests; never opens PRs.
- **Doc Updater** — finds stale names, missing entries, and outdated signatures in docs; edits minimally; never changes logic.
- **Test Auditor** — audits all test files after a batch of work; deletes tests violating quality rules (2+ mocks, no AAA, constructor assertions, type-check assertions); adds AAA comments where missing; never touches source code.

### The human gate

The human sits **after** the Orchestrator's Completion Report. No PR is opened until the human reviews the report and gives the go-ahead.

The Orchestrator will stop and ask for guidance if:
- The check suite cannot be made green after max retries
- An ExecPlan acceptance criterion cannot be satisfied by the code
- The Test Agent cannot write a meaningful failing test

## ExecPlans

ExecPlans define multi-step work. They live in `docs/exec-plans/active/` and
move to `docs/exec-plans/completed/` when the Orchestrator declares the task
done and the human archives them.

Use an ExecPlan when the work: spans more than two modules, requires research
before implementation, involves external APIs, or could take more than one
agent session.

## Development conventions (enforced mechanically)

```bash
pytest -v                    # all tests must pass
ruff check src/ tests/       # zero lint errors
mypy src/                    # zero type errors
```

Layer rule:
```
types → config → adapters → domain → services → cli
```

Test file placement:
- Unit tests: next to source, named `<module>_test.py`
- Integration tests: `tests/`
