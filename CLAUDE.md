# Audiobook Generator — Agent Guide

## What this is
A Python CLI that converts plain-text books (Project Gutenberg format) into
multi-voice audiobooks using ElevenLabs TTS. Characters are detected
automatically and assigned distinct voices. Output is a single assembled
audio file per book.

## Read first
- [ARCHITECTURE.md](ARCHITECTURE.md) — domain map, layer model, dependency rules
- [docs/DESIGN.md](docs/DESIGN.md) — design philosophy and non-negotiables
- [docs/product-specs/index.md](docs/product-specs/index.md) — what we're building

## How to navigate deeper
| Topic | Where to look |
|---|---|
| Active work / tasks | [docs/exec-plans/active/](docs/exec-plans/active/) |
| Tech debt | [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) |
| Core beliefs | [docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md) |
| Quality grades | [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md) |
| Security rules | [docs/SECURITY.md](docs/SECURITY.md) |
| ElevenLabs API patterns | [docs/references/elevenlabs-reference.md](docs/references/elevenlabs-reference.md) |
| Agent fleet | [.claude/agents/](.claude/agents/) |

## Working model
**Humans steer. Agents execute.**

Four agents collaborate in a TDD loop owned by the Orchestrator.
See [AGENTS.md](AGENTS.md) for the full workflow diagram.

```
Orchestrator     — owns a task end-to-end; drives the loop; verifies against ExecPlan
   │
   ├─► Test Agent    — writes failing _test.py files; confirms red; never touches impl
   │       │
   │       ▼
   │   Coder Agent   — writes minimum impl to pass tests; runs checks; reports PASS/FAIL
   │       │
   │       └─ (iterates with Orchestrator until green)
   │
   └─► Doc Updater   — detects doc/code drift after implementation; minimal edits only
```

The human gate sits **after** the Orchestrator's Completion Report. No PR is
opened until the human reviews and approves.

## ExecPlans
When implementing complex features or significant refactors, use an ExecPlan
as defined in [docs/PLANS.md](docs/PLANS.md). ExecPlans live in
`docs/exec-plans/active/` and move to `docs/exec-plans/completed/` when done.

Use an ExecPlan when the work: spans more than two modules, requires research
before implementation, involves external APIs, or could take more than one
agent session.

## Development workflow

Dependencies are pre-installed in the Docker image — do not run `pip install`
at the start of every task. The environment is ready when you start.

```bash
# Run tests (must pass before any PR)
pytest -v

# Lint and type-check (must pass before any PR)
ruff check src/
mypy src/

# Build and verify CLI entry point
python -m build
audiobook --help
```

If you add a new dependency to `pyproject.toml`, run:
```bash
pip install --quiet -e ".[dev]"
```
This is the only time a manual pip install is needed.

## Non-negotiables (enforced mechanically)
1. **TDD — test first, always** — write a failing test before any implementation; see core-beliefs #8
   Unit test files live next to the source file, named `<module>_test.py` (Go-style).
   `tests/` is for integration tests only.
2. **Typed models at every external boundary** — dataclasses with type annotations, no raw dicts crossing module edges
3. **100% test coverage on `domain/`** — enforced by pytest-cov CI gate
4. **Structured logging only** — `structlog`, never bare `print()` or `logging.info(str(...))` (design target, not fully implemented yet)
5. **Type annotations on all public functions** — mypy strict mode
6. **No API keys in source** — env vars only, validated at startup via `config` layer
7. **No `datetime.now()` or unseeded `random` in domain/services** — see core-beliefs #10

## Module dependency pattern
```
config → domain → (ai, parsers, downloader, tts, workflows) → main.py
```
The implementation uses a pragmatic module structure optimized for clarity. Parsers, AI, downloader, and workflows all depend on domain models. See ARCHITECTURE.md for details.

## Context limits
When a task requires deep context about a subsystem, read that subsystem's
module-level docstring first — it explains the module's purpose, constraints,
and key decisions. Module docstrings are the primary unit of in-repo knowledge.
