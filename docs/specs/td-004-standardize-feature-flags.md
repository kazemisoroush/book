# TD-004 — Standardize Feature Flags

## Goal

Create a unified feature flag system so that all "our" end-to-end features (ambient sound, cinematic SFX, emotion tags, voice design, scene context, etc.) can be toggled on/off at runtime through consistent, discoverable constructor parameters.

---

## Problem

Currently:
- **Ambient audio** and **cinematic SFX** have explicit boolean flags (`ambient_enabled`, `cinematic_sfx_enabled`)
- **Emotion tags**, **voice design**, **scene context**, and **LLM voice settings** are controlled implicitly (LLM output, dependency injection, or model selection)
- No centralized place to see all feature toggles
- No config file support for feature flags
- Each feature uses different control mechanisms (constructor param vs. client=None vs. model selection)

This makes it hard to:
- Document what features exist and how to enable/disable them
- Test feature combinations (e.g., SFX without ambient)
- Deploy with specific feature subsets
- Iterate quickly on audio quality by toggling features

---

## Concept

**Unified Feature Flags System**:

1. **Inventory** (DONE): Document all features and current flag status in `docs/FEATURE_FLAGS.md`
2. **Standardize** (TODO): Add explicit boolean flags for all major features
3. **Config file support** (TODO): Load flags from YAML/JSON at startup
4. **CLI exposure** (TODO): Allow users to toggle flags via command-line arguments

---

## Acceptance Criteria

1. ✅ Feature catalog created at `docs/FEATURE_FLAGS.md` listing all features, their current flag status, and control mechanisms
2. Add explicit boolean flags to `TTSOrchestrator` constructor for:
   - `emotion_enabled: bool = True` (currently implicit, LLM-driven)
   - `voice_design_enabled: bool = True` (currently implicit, client-based)
   - `scene_context_enabled: bool = True` (currently implicit, registry-based)
3. Update `TTSProjectGutenbergWorkflow.run()` to thread through all flags from CLI
4. New module `src/config/feature_flags.py`:
   - `FeatureFlags` dataclass with all feature toggles
   - `FeatureFlags.from_dict()` / `to_dict()` for serialization
   - `FeatureFlags.from_yaml(path)` and `from_json(path)` for loading from files
5. Update `scripts/run_workflow.py` CLI with `--enable-*` / `--disable-*` flags for each feature
6. Config file template at `config/features.example.yaml` showing all toggles and defaults
7. Update `docs/FEATURE_FLAGS.md` with instructions on how to use the new flags
8. All tests pass; no regressions

---

## Out of Scope

- Async model switching (context_params currently model-gated, would require API-aware session management)
- Inline emotion tags (v3 model feature, currently not used due to context_params requirement)
- ALL-CAPS emphasis (v3 model feature, currently not used)
- Breath pauses (US-017, not yet implemented)
- Background music (US-012, not yet implemented)

These are deferred to future work or out of scope.

---

## Key Design Decisions

### Why New Flags for Implicit Features?

Currently, emotion, voice design, and scene context are "always on" if their dependencies are present. Adding explicit flags allows:
- **Testing**: Verify that disabling a feature doesn't break the pipeline
- **Deployment**: Ship with specific feature subsets (e.g., no voice design to save API costs)
- **Documentation**: Clear contract about what's enabled by default
- **User intent**: Explicit statement of what the user wants, not implicit discovery

### Why Config File Support?

Allows non-developers to toggle features without code changes:
```yaml
features:
  ambient_sound: true
  cinematic_sfx: true
  emotion_tags: true
  voice_design: false  # Disable to save API costs
```

Then pass `--config config/production.yaml` at startup.

### Flag Names

Use consistent naming: `{feature}_enabled` for all toggles. This makes discovery easier:
```python
orchestrator = TTSOrchestrator(
    ...,
    ambient_enabled=True,           # Explicit
    cinematic_sfx_enabled=True,     # Explicit
    emotion_enabled=True,           # New
    voice_design_enabled=True,      # New
    scene_context_enabled=True,     # New
)
```

---

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/tts/tts_orchestrator.py` | Add `emotion_enabled`, `voice_design_enabled`, `scene_context_enabled` constructor params; thread into resolution logic |
| `src/config/feature_flags.py` | **NEW** — `FeatureFlags` dataclass with YAML/JSON serialization |
| `src/workflows/tts_project_gutenberg_workflow.py` | Update `run()` to accept and thread feature flags |
| `scripts/run_workflow.py` | Add CLI arguments: `--enable-emotion`, `--disable-ambient`, etc. |
| `config/features.example.yaml` | **NEW** — Example config file with all toggles and descriptions |
| `docs/FEATURE_FLAGS.md` | ✅ Created — Usage guide and recommendations |

---

## Implementation Notes

- TDD: write tests for `FeatureFlags` dataclass (serialization, defaults, YAML loading)
- Minimal mocks: flag loading is simple logic, deserves simple tests
- No breaking changes: new flags default to `True`, so existing code unaffected
- Feature flag checks should be cheap (single boolean read)

---

## Relationship to Other Specs

- **US-011** (Ambient Sound) — Already has `ambient_enabled` flag
- **US-023** (Cinematic SFX) — Already has `cinematic_sfx_enabled` flag
- **US-009/010** (Emotion Tags) — Implicit; this TD adds explicit flag
- **US-003/014** (Voice Design) — Implicit; this TD adds explicit flag
- **US-020** (Scene Context) — Implicit; this TD adds explicit flag

---

## Success Criteria

Users can:
1. View all available features and their status: `python scripts/run_workflow.py --help` (new `--enable-*` / `--disable-*` options)
2. Disable specific features for testing or cost savings: `python scripts/run_workflow.py --url <url> --disable-voice-design --disable-ambient`
3. Load flags from a config file: `python scripts/run_workflow.py --url <url> --config config/production.yaml`
4. Read `docs/FEATURE_FLAGS.md` and understand what each flag does and how it affects audio quality

