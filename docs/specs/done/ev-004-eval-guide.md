# EV-004: Eval Guide

## Goal

Write `docs/EVAL_GUIDE.md` — a short reference codifying when to use tests
vs evals, the golden-label pattern, threshold conventions, and naming rules.

## Acceptance criteria

1. `docs/EVAL_GUIDE.md` exists and covers:
   - **When to use tests vs evals** — deterministic → pytest, non-deterministic → eval
   - **Plant / Run / Score** pattern (eval equivalent of AAA)
   - **Golden-label conventions** — real text, human-verifiable, minimum 3 passages
   - **Threshold rules** — 100% for agent evals, 80% for AI evals
   - **Naming conventions** — `score_<feature>.py`, `golden_<feature>.py`,
     `planted_<feature>.py`
   - **Recall vs precision** — what each measures, when to add each
   - **Running evals** — CLI commands, cost expectations
   - **Adding a new eval** — step-by-step checklist

2. `CLAUDE.md` links to the new guide in the "Read first" or table section.

3. The guide is under 150 lines (concise, not a novel).

## Out of scope

- Changing existing evals
- Tooling or automation

## Files expected to change

- `docs/EVAL_GUIDE.md` — new
- `CLAUDE.md` — add link
