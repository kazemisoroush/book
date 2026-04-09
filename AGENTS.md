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

### Orchestrator workflow (`agents/orchestrator/`)

| Agent | File | Role |
|---|---|---|
| Orchestrator | `.claude/agents/orchestrator/orchestrator.md` | Owns a task end-to-end |
| Test Agent | `.claude/agents/orchestrator/test-agent.md` | Writes failing tests only |
| Coder Agent | `.claude/agents/orchestrator/coder-agent.md` | Writes minimum implementation |

### Audit workflow (`agents/audit/`)

| Agent | File | Role |
|---|---|---|
| Audit Hook | `.claude/agents/audit/audit-hook.md` | Runs all three auditors after Orchestrator |
| Doc Auditor | `.claude/agents/audit/doc-auditor.md` | Fixes doc/code drift |
| Test Auditor | `.claude/agents/audit/test-auditor.md` | Removes low-value tests, enforces AAA |
| Dead Code Remover | `.claude/agents/audit/dead-code-remover.md` | Finds and removes unused code |

### Shared (`agents/shared/`)

| Agent | File | Role |
|---|---|---|
| Git Ops | `.claude/agents/shared/git-ops.md` | Handles git commits and version control |
| CI/CD Fixer | `.claude/agents/shared/ci-cd-fixer.md` | Diagnoses and fixes GitHub Actions failures |
| Spec Writer | `.claude/agents/shared/spec-writer.md` | Captures feature requests as structured specs |

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
Audit Hook
   ├─► [Pre-flight] Check if GitHub Actions is broken
   │   │
   │   ├─ YES ──► CI/CD Fixer
   │   │          └─ diagnoses latest failed run
   │   │          └─ replicates issue locally
   │   │          └─ implements and tests fix
   │   │          └─ pushes to remote branch
   │   │          └─ returns CI/CD Fixer report
   │   │
   │   └─ NO ──► proceed to standard auditors
   │
   ├─► Doc Auditor
   │   └─ receives list of changed files
   │   └─ finds drift between code and docs
   │   └─ makes minimal edits
   │
   ├─► Test Auditor
   │   └─ audits all *_test.py files
   │   └─ removes quality-rule violations
   │   └─ adds AAA comments where missing
   │
   ├─► Dead Code Remover
   │   └─ scans src/ for unused imports, functions, classes
   │   └─ verifies each candidate with grep cross-check
   │   └─ removes confirmed dead code
   │
   └─ confirms check suite green, returns combined report
   │
   ▼
Orchestrator emits Completion Report
   └─ human reviews and decides whether to open PR
```

### Agent responsibilities (one-line each)

- **Orchestrator** — decomposes work, drives the loop, verifies against the plan, hands off to Audit Hook.
- **Test Agent** — writes failing tests that precisely specify behaviour; never touches implementation.
- **Coder Agent** — writes the minimum code to make tests pass; never modifies tests; never opens PRs.
- **Audit Hook** — runs Doc Auditor, Test Auditor, and Dead Code Remover in sequence after the Orchestrator's verification passes; returns a combined report.
- **Doc Auditor** — finds stale names, missing entries, and outdated signatures in docs; edits minimally; never changes logic.
- **Test Auditor** — audits all test files after a batch of work; deletes tests violating quality rules (2+ mocks, no AAA, constructor assertions, type-check assertions); adds AAA comments where missing; never touches source code.
- **Dead Code Remover** — finds unused imports, functions, classes, and variables in `src/`; verifies each candidate with grep; removes confirmed dead code; never touches tests.
- **CI/CD Fixer** — fetches the latest GitHub Actions run, diagnoses the failure reason, replicates the issue locally, fixes it, and pushes to the remote branch; runs independently from the main TDD loop.
- **Spec Writer** — transforms rough feature requests into structured US/TD/RS/EV specs under `docs/specs/`; assigns IDs, writes acceptance criteria, updates the index; never writes implementation code.

### The human gate

The human sits **after** the Orchestrator's Completion Report. No PR is opened until the human reviews the report and gives the go-ahead.

The Orchestrator will stop and ask for guidance if:
- The check suite cannot be made green after max retries
- An ExecPlan acceptance criterion cannot be satisfied by the code
- The Test Agent cannot write a meaningful failing test

## Specs

All work is tracked as a spec in `docs/specs/`. Each spec contains a goal,
acceptance criteria, and out of scope. Use a spec when the work: spans more
than two modules, requires research before implementation, involves external
APIs, or could take more than one agent session.

## Development conventions (enforced mechanically)

```bash
pytest -v                    # all tests must pass
ruff check src/ tests/       # zero lint errors
mypy src/                    # zero type errors
```

Layer rule:
```
config → domain → (ai, parsers, downloader, repository, tts, workflows) → main.py
```

Test file placement:
- Unit tests: next to source, named `<module>_test.py`
- Integration tests: `tests/`
