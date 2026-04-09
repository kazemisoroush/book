# EV-001: Eval framework refactor

## Goal

Extract a shared `EvalHarness` base class from the existing `score_*.py` eval
scripts. Each eval becomes a short subclass that defines fixtures, checks, and
cleanup — the lifecycle, reporting, and CLI boilerplate live in the framework.

## Problem

The 8 existing eval scripts (`score_ai_read.py`, `score_git_ops.py`,
`score_ci_cd_fixer.py`, `score_orchestrator.py`, `score_test_agent.py`,
`score_test_auditor.py`, `score_doc_auditor.py`, `score_dead_code_remover.py`,
`score_design_auditor.py`) each duplicate:

- The `setup / score / cleanup` CLI dispatch (~15 lines)
- The recall/precision report formatting (~30 lines)
- The PASS/FAIL threshold logic
- The `_run()` subprocess helper

Each file is 150–300 lines when 50–80 would suffice.

## Acceptance criteria

1. A new module `src/evals/eval_harness.py` exists with a base class
   `EvalHarness` (or similar) that provides:
   - `setup()` / `score()` / `cleanup()` lifecycle with `__main__` CLI dispatch
   - `_run_cmd(cmd, timeout)` subprocess helper with timeout
   - `_git(cmd)` git helper
   - A `report(recall_checks, precision_checks, threshold)` method that prints
     the standard report format and returns the overall PASS/FAIL
   - A `state_file` property for persisting baseline state between setup and score

2. At least 3 existing eval scripts are migrated to use the harness:
   - `score_git_ops.py` (agent eval with git state)
   - `score_ci_cd_fixer.py` (agent eval with code fixes)
   - `score_test_agent.py` (agent eval with test quality)

3. Each migrated eval is shorter than before (measured by line count).

4. All migrated evals still produce identical output when run
   (`setup` / `score` / `cleanup` still work, same checks, same format).

5. `ruff check` and `mypy` pass on all new and modified files.

6. Existing non-migrated evals are NOT broken (they can be migrated later).

## Out of scope

- Migrating ALL evals (just 3 to prove the pattern)
- Changing what each eval checks (only extracting shared code)
- Adding new evals
- The Eval Agent or Eval Auditor (separate specs)

## Files expected to change

- `src/evals/eval_harness.py` — new shared framework
- `src/evals/score_git_ops.py` — migrated
- `src/evals/score_ci_cd_fixer.py` — migrated
- `src/evals/score_test_agent.py` — migrated
