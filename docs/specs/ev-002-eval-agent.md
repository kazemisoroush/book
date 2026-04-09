# EV-002: Eval Agent

## Goal

Add an Eval Agent to the agent fleet. It writes evals for AI-based features
the same way the Test Agent writes tests for deterministic features. It follows
a TDD-inspired flow: **Plant → Run → Score** (the eval equivalent of
Arrange → Act → Assert).

## Motivation

Today, evals are written manually. When a new AI feature ships (e.g. scene
detection, emotion tagging), nobody writes an eval until much later — if at all.
The Eval Agent closes this gap: the Orchestrator dispatches it for any step
that involves non-deterministic AI output, just as it dispatches the Test Agent
for deterministic code.

## How it fits in the Orchestrator workflow

```
Orchestrator
  │
  ├─ Deterministic step → Test Agent → Coder Agent (existing)
  │
  └─ AI/non-deterministic step → Eval Agent → Coder Agent
       │
       ├─ Writes golden labels (fixtures)
       ├─ Writes scorer (using EvalHarness base class)
       ├─ Runs eval against real LLM to establish baseline
       └─ Reports baseline score (not necessarily 100%)
```

## Acceptance criteria

1. A new agent definition exists at `.claude/agents/orchestrator/eval-agent.md`
   with proper frontmatter (name, description, tools).

2. The agent prompt specifies:
   - It writes golden-label fixtures in `src/evals/fixtures/`
   - It writes a scorer that subclasses `EvalHarness` from `eval_harness.py`
   - It runs the eval against the real LLM to establish a baseline score
   - It reports the baseline (recall %, precision %, pass/fail at threshold)
   - It never writes implementation code
   - It follows the **Plant / Run / Score** structure

3. The agent prompt includes conventions:
   - Golden labels must be human-verifiable (real text, not synthetic)
   - Each eval must have at least 1 recall check and 1 precision check
   - Threshold is 80% for AI evals (vs 100% for agent evals)
   - Scorer file naming: `score_<feature>.py`
   - Fixture file naming: `golden_<feature>.py` or `planted_<feature>.py`

4. The agent has an eval harness at `src/evals/score_eval_agent.py` that:
   - Gives the Eval Agent a small AI behaviour to eval (e.g. "emotion detection
     on 3 passages")
   - Checks the written eval has: golden labels, scorer subclassing EvalHarness,
     recall + precision checks, baseline score reported
   - Verifies the scorer runs without error
   - Scores recall (did it write all required components?) and precision
     (did it follow conventions?)

5. `ruff check` and `mypy` pass on all new files.

## Out of scope

- Modifying the Orchestrator prompt (that's a follow-up after this ships)
- The Eval Auditor (Spec 3)
- Migrating existing evals to the new pattern

## Files expected to change

- `.claude/agents/orchestrator/eval-agent.md` — new agent definition
- `src/evals/score_eval_agent.py` — eval for the Eval Agent
- `src/evals/fixtures/planted_eval_agent_spec.md` — spec fixture for the eval
