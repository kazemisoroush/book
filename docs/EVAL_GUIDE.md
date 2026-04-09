# Eval Guide

## When to use tests vs evals

**Tests (pytest)** — deterministic behavior, exact assertions:
- Data transforms, domain logic, adapters with known inputs/outputs

**Evals (Plant / Run / Score)** — non-deterministic or requires human judgment:
- LLM features (character detection, speaker attribution)
- Agent behavior (Test Agent follows conventions?)
- Design decisions that cannot be mechanically verified

## Plant / Run / Score pattern

Three-phase pattern (eval equivalent of Arrange / Act / Assert):

**Plant** — Create fixtures, write files, record baseline state
**Run** — Execute system under test (agent manually, or AI layer directly)
**Score** — Check recall/precision, report PASS/FAIL with threshold logic

## Golden-label conventions

Human-annotated ground truth for AI/LLM features. Use real text from the domain (not synthetic), human-verifiable annotations, minimum 3 passages ordered by difficulty. Store in `src/evals/fixtures/golden_*.py` as typed dataclasses with metadata.

## Threshold rules

**Agent evals:** 100% pass rate (conventions are deterministic)
**AI evals:** 80% pass rate (LLM behavior is non-deterministic)

```python
passed = recall_pct == 1.0 and precision_pct == 1.0  # agents
passed = recall_pct >= 0.8 and precision_pct >= 0.8  # AI
```

## Naming conventions

All eval files in `src/evals/` or `src/evals/fixtures/`.

- `score_<feature>.py` — main eval script (subclasses `EvalHarness` for agents)
- `golden_<feature>.py` — human-annotated ground truth (AI evals)
- `planted_<feature>.py` — planted code/files (agent evals)
- `planted_<feature>_test.py` — planted test files (if needed)

## Recall vs precision

**Recall** — Completeness (did we find all expected items?)
**Precision** — Accuracy (did we avoid false positives / damage?)

Agent evals: heavy on precision (avoid breaking conventions, wrong files).
AI evals: heavy on recall (find all characters, dialogue segments).

## Running evals

**Agent evals (three-step):**
```bash
# 1. Plant fixtures
python -m src.evals.score_doc_auditor setup

# 2. Run the agent manually (via Claude Code or CLI)
# Follow the prompt printed by setup

# 3. Score results
python -m src.evals.score_doc_auditor score

# 4. Clean up
python -m src.evals.score_doc_auditor cleanup
```

**AI evals (one-step):**
```bash
# Run end-to-end (Plant + Run + Score in one command)
python -m src.evals.score_ai_read

# Run a specific passage
python -m src.evals.score_ai_read --passage simple_dialogue
```

**Cost expectations:**
- Agent evals: free (no API calls)
- AI evals: $0.10–$2.00 per run (depends on passage count and LLM size)

**Hard rule — no e2e pipeline tests:**
Never run end-to-end tests that exercise the parse → AI → TTS pipeline.
These hit paid APIs (ElevenLabs, LLMs) and are prohibitively expensive.
Unit tests and `make test` / `make lint` are the verification boundary.
This applies to all agents, evals, and the Orchestrator.

## Adding a new eval

**For agent behavior:**
1. Create `score_<agent>.py` subclassing `EvalHarness`
2. Create `planted_<scenario>.py` fixture in `fixtures/`
3. Implement `setup()` — plant the fixture, print instructions
4. Implement `score()` — check recall (did it do the thing?) and precision (did it avoid damage?)
5. Implement `cleanup()` — remove planted files, revert state
6. Add recall/precision checks as tuples: `(tag, description, passed)`
7. Set threshold: 100% for agent evals
8. Test the eval: run setup, invoke agent, run score, verify PASS/FAIL logic

**For AI/LLM features:**
1. Create `golden_<feature>.py` with typed dataclass + 3+ passages
2. Create `score_<feature>.py` (no need to subclass `EvalHarness`)
3. Implement single entry point that calls the AI layer and scores results
4. Add recall checks (completeness) and precision checks (accuracy)
5. Set threshold: 80% for AI evals
6. Document cost and runtime in module docstring
7. Test with `--passage <name>` flag for debugging individual cases
