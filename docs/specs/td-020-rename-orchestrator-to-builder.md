# TD-020 — Rename Orchestrator Agent to Builder

## Goal

Rename the Orchestrator agent (`.claude/agents/orchestrator/`) to "Builder"
to eliminate naming confusion with the `TTSOrchestrator` class. The agent
builds features end-to-end via the TDD loop — "Builder" is more accurate
than "Orchestrator".

---

## Problem

The project has both an Orchestrator **agent** (drives the TDD loop, owns
task delivery) and a `TTSOrchestrator` **class** (assembles chapter audio).
When discussing "the orchestrator" in code reviews, docs, or debugging, it's
unclear which one is meant.

The agent's role is closer to a builder: it takes a spec, constructs the
implementation through Test Agent → Coder Agent cycles, and delivers a PR.
Renaming the agent to "Builder" resolves the ambiguity.

---

## Acceptance criteria

1. `.claude/agents/orchestrator/` directory is renamed to `.claude/agents/builder/`.
2. `.claude/agents/orchestrator/orchestrator.md` becomes `.claude/agents/builder/builder.md`
   with all internal references updated (name field, description, headings).
3. `.claude/agents/orchestrator/test-agent.md` moves to `.claude/agents/builder/test-agent.md`.
4. `.claude/agents/orchestrator/coder-agent.md` moves to `.claude/agents/builder/coder-agent.md`.
5. All markdown files that reference the Orchestrator agent are updated:
   - `CLAUDE.md`
   - `AGENTS.md`
   - `.claude/agents/audit/audit-hook.md`
   - `.claude/agents/audit/clean-code-auditor.md`
   - `.claude/agents/shared/spec-writer.md`
   - `docs/EVAL_GUIDE.md`
   - Any spec files in `docs/specs/` referencing the agent
6. All existing tests continue to pass (`pytest -v`).
7. `ruff check src/` and `mypy src/` produce no errors.

---

## Out of scope

- Renaming `TTSOrchestrator` class (separate concern, not part of this spec)
- Changing agent behaviour or workflow logic
- Updating completed specs in `docs/specs/done/` (historical record stays as-is)

---

## Files changed (expected)

| File | Change |
|---|---|
| `.claude/agents/orchestrator/` | Rename directory to `.claude/agents/builder/` |
| `.claude/agents/builder/builder.md` | Rename from orchestrator.md; update name, description, headings |
| `.claude/agents/builder/test-agent.md` | Move from orchestrator/ (content unchanged) |
| `.claude/agents/builder/coder-agent.md` | Move from orchestrator/ (content unchanged) |
| `CLAUDE.md` | Update agent references |
| `AGENTS.md` | Update agent references and workflow diagram |
| `.claude/agents/audit/audit-hook.md` | Update references |
| `.claude/agents/audit/clean-code-auditor.md` | Update references if present |
| `.claude/agents/shared/spec-writer.md` | Update references |
| `docs/EVAL_GUIDE.md` | Update references |

---

## Relationship to other specs

- **TD-015** (Replace Orchestrator Class Constants): References the TTSOrchestrator class, not the agent — no update needed.
- **TD-014** (Break Circular TTS Orchestrator Imports): References the TTSOrchestrator class — no update needed.
