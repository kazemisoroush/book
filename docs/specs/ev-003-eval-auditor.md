# EV-003: Eval Auditor

## Goal

Add an Eval Auditor agent that audits eval quality the same way the Test
Auditor audits test quality. It runs after evals are written (by the Eval
Agent or manually) and enforces eval conventions.

## Acceptance criteria

1. Agent definition at `.claude/agents/audit/eval-auditor.md` with proper
   frontmatter.

2. The agent checks every `score_*.py` file in `src/evals/` for:
   - Subclasses `EvalHarness` (or follows the same lifecycle if standalone)
   - Has at least 1 recall check and 1 precision check
   - Has a `cleanup()` that removes all planted files
   - Golden-label fixtures exist and are non-empty
   - Scorer runs without import errors (`python -c "import src.evals.score_X"`)
   - No hardcoded API responses (no mocking the AI provider in evals)
   - File naming follows convention (`score_<feature>.py`, `golden_<feature>.py`)

3. The agent fixes what it can (missing cleanup entries, import errors) and
   reports what it cannot (missing recall/precision checks, missing fixtures).

4. An eval exists at `src/evals/score_eval_auditor.py` that validates the
   Eval Auditor catches planted violations.

5. `ruff check` passes on all new files.

## Out of scope

- Modifying existing evals (the auditor reports, doesn't rewrite)
- Integrating into the Audit Hook (follow-up)

## Files expected to change

- `.claude/agents/audit/eval-auditor.md` — new agent
- `src/evals/score_eval_auditor.py` — eval for the Eval Auditor
