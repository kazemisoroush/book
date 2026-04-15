# Eval Guide

## When to use tests vs evals

**Tests (pytest)** — deterministic behavior, exact assertions:
- Data transforms, domain logic, adapters with known inputs/outputs

**Evals (Plant / Run / Score)** — non-deterministic or requires human judgment:
- Agent behavior (Test Agent follows conventions?)
- Design decisions that cannot be mechanically verified

**Evals (promptfoo)** — LLM prompt quality and AI pipeline behavior:
- Character detection, speaker attribution, segmentation quality
- Emotion detection, sound effect detection, feature completeness
- Announcement formatting quality

## AI evals (promptfoo)

AI/LLM evals use [promptfoo](https://www.promptfoo.dev/) for declarative
evaluation of prompt+model combinations. Configuration is in
`promptfooconfig.yaml` at the repo root.

### Running AI evals

```bash
# Run all AI evals
npx promptfoo@0.103.0 eval

# Run a specific eval suite by description filter
npx promptfoo@0.103.0 eval --filter-description "ai-read"
npx promptfoo@0.103.0 eval --filter-description "feature-completeness"
npx promptfoo@0.103.0 eval --filter-description "sfx"
npx promptfoo@0.103.0 eval --filter-description "announcements"

# View results in browser
npx promptfoo@0.103.0 view
```

### Eval suites

| Suite | Description | Replaces |
|---|---|---|
| `ai-read` | Character detection, segmentation, speaker attribution | `score_ai_read.py` |
| `feature-completeness` | All AI features together: types, emotions, scenes, voice settings | `score_ai_feature_completeness.py` |
| `sfx` | Sound effect detection recall and precision | `score_sound_effect_detection.py` |
| `announcements` | Book title and chapter announcement formatting | `score_announcements.py` |

### Custom providers

Promptfoo uses custom Python providers that call the real application stack:

- `evals/providers/bedrock_section_parser.py` — calls PromptBuilder + AISectionParser + AWSBedrockProvider
- `evals/providers/bedrock_announcements.py` — calls AnnouncementFormatter + AWSBedrockProvider

### Prompt templates

Prompts are stored as template files in `src/parsers/prompts/` and loaded by
both the application and the promptfoo providers:

- `src/parsers/prompts/section_parser.prompt` — main segmentation prompt
- `src/parsers/prompts/book_title.prompt` — book title formatting
- `src/parsers/prompts/chapter_announcement.prompt` — chapter announcement formatting

### Cost expectations

- AI evals: $0.10–$2.00 per run (depends on passage count and LLM)

## Agent evals (Plant / Run / Score)

### Three-phase pattern

**Plant** — Create fixtures, write files, record baseline state
**Run** — Execute system under test (agent manually, or AI layer directly)
**Score** — Check recall/precision, report PASS/FAIL with threshold logic

### Running agent evals

```bash
# 1. Plant fixtures
python -m src.evals.harness.score_doc_auditor setup

# 2. Run the agent manually (via Claude Code or CLI)
# Follow the prompt printed by setup

# 3. Score results
python -m src.evals.harness.score_doc_auditor score

# 4. Clean up
python -m src.evals.harness.score_doc_auditor cleanup
```

### Threshold rules

**Agent evals:** 100% pass rate (conventions are deterministic)
**AI evals (promptfoo):** 80% pass rate (LLM behavior is non-deterministic)

## Naming conventions

Eval files are organized as follows:

- `promptfooconfig.yaml` — AI/LLM evals (promptfoo configuration)
- `evals/providers/` — custom promptfoo providers
- `src/evals/harness/` — evals for the Claude Code agent fleet (orchestrator, auditors, etc.)
- `src/evals/harness/fixtures/` — planted fixtures for harness evals
- `src/evals/eval_harness.py` — base class for agent evals

File naming for agent evals:
- `score_<feature>.py` — main eval script (subclasses `EvalHarness`)
- `planted_<feature>.py` — planted code/files (agent evals)
- `planted_<feature>_test.py` — planted test files (if needed)

## Recall vs precision

**Recall** — Completeness (did we find all expected items?)
**Precision** — Accuracy (did we avoid false positives / damage?)

Agent evals: heavy on precision (avoid breaking conventions, wrong files).
AI evals: heavy on recall (find all characters, dialogue segments).

**Hard rule — no e2e pipeline tests:**
Never run end-to-end tests that exercise the parse → AI → TTS pipeline.
These hit paid APIs (ElevenLabs, LLMs) and are prohibitively expensive.
Unit tests and `make test` / `make lint` are the verification boundary.
This applies to all agents, evals, and the Orchestrator.

## Adding a new AI eval

1. Add test cases to `promptfooconfig.yaml` with descriptive `description` tags
2. Use existing custom providers or create new ones in `evals/providers/`
3. Use `python` assertion type for complex validation logic
4. Use `contains`/`not-contains` for simple substring checks
5. Run `npx promptfoo@0.103.0 eval --filter-description "your-suite"` to verify

## Adding a new agent eval

1. Create `src/evals/harness/score_<agent>.py` subclassing `EvalHarness`
2. Create `planted_<scenario>.py` fixture in `src/evals/harness/fixtures/`
3. Implement `setup()` — plant the fixture, print instructions
4. Implement `score()` — check recall and precision
5. Implement `cleanup()` — remove planted files, revert state
6. Set threshold: 100% for agent evals
