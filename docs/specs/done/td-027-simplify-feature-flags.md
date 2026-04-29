# TD-027 — Simplify Feature Flags

## Goal

Reduce the feature-flag system to a single, simple concept: hardcoded
deterministic toggles in `src/config/feature_flags.py`. Eliminate CLI flags,
env vars, YAML loading, and prompt-level "flags" that were never actually
toggles at all.

## Problem

The current system (shipped by TD-004) has the same five flags declared in
three independent places, with a broken wiring path, and three flags that only
mutate prompt text rather than gating any code:

- `FeatureFlags` dataclass at `src/config/feature_flags.py`
- `CLIConfig` fields at `src/config/config.py:130-134`
- Argparse `--enable-*` / `--disable-*` pairs at `src/config/config.py:182-191`

Concrete bugs:

1. `CLIConfig.run_kwargs()` splats `ambient_enabled=…` into `workflow.run(**kwargs)`,
   but no workflow's `run()` accepts those kwargs — `--disable-ambient` crashes
   with `TypeError` today.
2. `emotion_enabled`, `voice_design_enabled`, `scene_context_enabled` only
   toggle Jinja `{% if %}` blocks in `src/parsers/prompts/section_parser.prompt`
   and JSON-example construction in `src/parsers/prompt_builder.py`. They do
   nothing deterministic. Flipping them off merely asks the LLM not to emit a
   field — cached JSON still gets applied unchanged.
3. `chapter_announcer_enabled` exists on `FeatureFlags` but has no CLI / env /
   YAML surface — unreachable from outside.
4. `AudioAssembler` re-declares `ambient_enabled` / `sound_effects_enabled` as
   loose constructor booleans, making them a fourth source of truth.
5. Docs reference `FeatureFlags.from_yaml`, `from_json`, `load`,
   `scripts/run_workflow.py`, and the prompt-flag gating in
   `AudioOrchestrator` — none of which exist.
6. `config/features.example.yaml` exists but nothing reads it.
7. `AudioOrchestrator.DEBUG = False` class constant is dead.

The user's rule is: **flags should only affect the deterministic part of the
code**. Prompt variants are not flags.

## Concept

**Feature flags are hardcoded values in `src/config/feature_flags.py`.** They
are not configurable from CLI, env, or YAML. To try the pipeline without a
feature, edit the file. If a flag later needs to be configurable, it graduates
into `src/config/config.py` as a proper config value — but that is a future
decision, not this spec.

**Prompt content is not a flag.** The prompt is static and is the single source
of truth shared with promptfoo evals. Optional LLM output fields stay optional
at the schema level, not via template conditionals.

## Acceptance Criteria

1. `src/config/feature_flags.py` contains a `FeatureFlags` dataclass with
   exactly three fields, all deterministic toggles:
   - `ambient_enabled: bool = True` — gate ambient mixing
   - `sound_effects_enabled: bool = True` — gate SFX / vocal-effect rendering
   - `chapter_announcer_enabled: bool = True` — gate synthetic chapter intros
2. `FeatureFlags` has no `to_dict` / `from_dict` / `from_yaml` / `from_json`
   methods. It is a plain dataclass.
3. `CLIConfig` (`src/config/config.py`) has no feature-flag fields and no
   `--enable-*` / `--disable-*` argparse arguments. `run_kwargs()` returns only
   legitimate invocation parameters.
4. `src/parsers/prompts/section_parser.prompt` contains no Jinja `{% if %}`
   conditionals for feature flags. The prompt is static.
5. `src/parsers/prompt_builder.py` no longer receives or consults a
   `FeatureFlags` argument. The JSON-example construction is unconditional.
6. `src/audio/audio_assembler.py` accepts a `FeatureFlags` instance (not loose
   booleans) and reads `ambient_enabled` / `sound_effects_enabled` from it.
7. `src/audio/audio_orchestrator.py` has no `DEBUG` class constant. Its
   constructor accepts a single `feature_flags: FeatureFlags` parameter
   (plus existing non-flag params) and passes the same object to
   `AudioAssembler`.
8. `src/workflows/ai_workflow.py` accepts an optional `FeatureFlags` in its
   `run()` signature. `main.py` instantiates `FeatureFlags()` once and passes
   it through explicitly. No flat-kwargs splat path.
9. Deleted artifacts:
   - `config/features.example.yaml`
   - `docs/FEATURE_FLAGS.md` (or rewritten to a ~20-line page describing the
     new hardcoded model)
   - Any stale `scripts/run_workflow.py` references in docs
   - The old `emotion_enabled`, `voice_design_enabled`, `scene_context_enabled`
     fields everywhere they appear
10. All tests pass. Tests that previously asserted prompt-flag behavior are
    either deleted (if they tested removed functionality) or rewritten against
    the static prompt.
11. `ruff check src/` and `mypy src/` pass.
12. `ARCHITECTURE.md` references to `FeatureFlags.from_yaml` etc. are removed.

## Out of Scope

- Making feature flags configurable from CLI / env / YAML. Deferred.
- Adding new feature flags.
- Changing how prompts are structured beyond removing the flag conditionals.
- Touching `debug` — stays on `CLIConfig` as an invocation flag, not a feature
  flag. Dead `AudioOrchestrator.DEBUG` constant is deleted as cleanup only.

## Key Design Decisions

### Why hardcoded?

Runtime-togglable feature flags are a premature abstraction for a single-user
CLI tool. The cost of a CLI/env/YAML surface (three sources of truth, broken
wiring, doc drift) exceeded the benefit of runtime configurability. Editing
one file is an acceptable cost for a rare operation. If usage patterns later
demand configurability, individual flags can graduate into `config.py`.

### Why delete the prompt-level flags?

They violate the invariant "flags only affect deterministic code". They gave
the illusion of disabling a feature while actually only asking the LLM nicely
not to emit it. The schema already treats emotion/voice_design/scene as
optional fields — an LLM that skips them is supported; an LLM that emits them
is supported. No flag needed.

### Why keep `sound_effects_enabled`?

Unlike the prompt-level flags, it has a deterministic effect in `AudioAssembler`
(skips SFX rendering). After this cleanup it becomes a pure deterministic
gate — the prompt always tells the LLM about SFX; the audio layer decides
whether to render them.

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/config/feature_flags.py` | Trim to 3 fields; delete `to_dict`/`from_dict` |
| `src/config/config.py` | Delete feature-flag fields and argparse args from `CLIConfig`; simplify `run_kwargs` |
| `src/parsers/prompt_builder.py` | Remove `FeatureFlags` param; unconditional JSON example |
| `src/parsers/prompts/section_parser.prompt` | Remove all `{% if %}` feature-flag conditionals |
| `src/audio/audio_assembler.py` | Accept `FeatureFlags` instead of loose bools |
| `src/audio/audio_orchestrator.py` | Delete `DEBUG` constant; pass `FeatureFlags` to assembler |
| `src/workflows/ai_workflow.py` | Keep `feature_flags` param; no behavior change |
| `src/main.py` | Instantiate `FeatureFlags()` and pass to `workflow.run` |
| `config/features.example.yaml` | **DELETE** |
| `docs/FEATURE_FLAGS.md` | Rewrite minimally or delete |
| `ARCHITECTURE.md` | Remove stale `from_yaml` references |
| `src/config/feature_flags_test.py` | Trim tests to match minimal surface |
| `src/config/config_test.py` | Remove tests for deleted argparse args |
| `src/parsers/prompt_builder_test.py` | Remove flag-gated test cases |
| `src/audio/audio_assembler_test.py` | Update to new constructor signature |

## Implementation Notes

- No backwards compatibility. Delete cleanly; do not leave shims or deprecated
  aliases. The user has explicitly opted out of back-compat.
- TDD: write/adjust failing tests first per the Builder loop.
- After implementation, run `make verify` to confirm the end-to-end pipeline
  still produces correct `output.json`.
