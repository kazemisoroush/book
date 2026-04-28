# TD-029 — Split ElevenLabs TTS Provider into v2 and v3

## Goal

Split the single `ElevenLabsTTSProvider` class into two separate, end-to-end
provider implementations — one per ElevenLabs model generation — with no
shared runtime capability gating and no backwards-compatibility concerns.

- `ElevenLabsV2TTSProvider` — pinned to `eleven_multilingual_v2`, uses
  `previous_text` / `next_text` / `previous_request_ids` for prosody
  continuity. No inline audio tags. No ALL-CAPS emphasis handling.
- `ElevenLabsV3TTSProvider` — pinned to `eleven_v3`, uses inline audio
  tags (`[whispers]`, `[sarcastic]`, …) and ALL-CAPS word stress. No
  context-params path.

Each provider is a standalone class in its own file, with its own test file,
its own name (`"elevenlabs_v2"` / `"elevenlabs_v3"`), and no branches on a
capability table.

## Problem

`src/audio/tts/elevenlabs_tts_provider.py` is currently one class that
behaves as two providers, switched by a module-level `_MODEL_ID` string and
a `_MODEL_CAPS` dict at `src/audio/tts/elevenlabs_tts_provider.py:39-53`:

```python
_MODEL_ID = "eleven_multilingual_v2"

_MODEL_CAPS: dict[str, dict[str, bool]] = {
    "eleven_v3": {"inline_tags": True,  "allcaps_emphasis": True,  "context_params": False},
    "eleven_multilingual_v2": {"inline_tags": False, "allcaps_emphasis": False, "context_params": True},
}
```

Concrete problems:

1. **Capability gating is runtime-dynamic for a value that never changes at
   runtime.** Switching model requires editing a module-level constant;
   there is no legitimate scenario where one process needs both models. The
   gating adds code paths the type system can never prove correct.
2. **`synthesize()` is a switch statement disguised as polymorphism** —
   three `if caps[...]:` branches at
   `src/audio/tts/elevenlabs_tts_provider.py:190`, `:228`, and the implicit
   branch on `_is_emotional` inside the tag-prepend path. Each branch has
   v2-only or v3-only meaning.
3. **Single `name = "elevenlabs"` erases which model produced a cached
   beat.** Two runs with different `_MODEL_ID` values collide on disk paths
   (`books/<id>/audio/tts/elevenlabs/beat_NNNN.mp3`), so cached outputs from
   one model are silently served to the other.
4. **Test file is 600+ lines covering two disjoint feature sets.** Classes
   `TestElevenLabsTTSProviderInlineTags` and `TestElevenLabsTTSProviderContextParams`
   exercise mutually exclusive branches; every inline-tags test monkeypatches
   `_MODEL_ID = "eleven_v3"` to flip globally. That pattern is fragile and
   leaks state across tests.
5. **Module docstring documents a dual-model contract** that the project's
   provider naming rule (`{Vendor}{Capability}Provider`) doesn't express.
   There is no `{Model}` slot in the naming convention because the
   convention assumes one provider = one backend.

## Concept

**One provider per ElevenLabs model generation, end-to-end.** No shared
capability table, no `_MODEL_ID` constant, no monkeypatching in tests. Each
provider hardcodes the single model it speaks to and implements only the
parameters that model supports.

**Names disambiguate cache directories.** `name` becomes `"elevenlabs_v2"`
and `"elevenlabs_v3"`, so `books/<id>/audio/tts/elevenlabs_v2/` and
`.../elevenlabs_v3/` never collide.

**No backwards compatibility.** Delete `ElevenLabsTTSProvider` and its test
file outright. Do not keep a shim, alias, re-export, or deprecation warning.
Callers (currently none in production — only tests reference the class) are
updated to pick a specific version.

## Acceptance Criteria

1. `src/audio/tts/elevenlabs_v2_tts_provider.py` exists and contains a
   class `ElevenLabsV2TTSProvider(TTSProvider)` with:
   - `name` property returning `"elevenlabs_v2"`
   - Hardcoded `model_id = "eleven_multilingual_v2"` (module-level constant
     or class attribute — no dict lookup)
   - `synthesize()` signature including `previous_text`, `next_text`,
     `previous_request_ids`; forwards them to the API unconditionally
   - No `emotion`-to-inline-tag prepending
   - No reference to inline tags, ALL-CAPS emphasis, or any capability dict
2. `src/audio/tts/elevenlabs_v3_tts_provider.py` exists and contains a
   class `ElevenLabsV3TTSProvider(TTSProvider)` with:
   - `name` property returning `"elevenlabs_v3"`
   - Hardcoded `model_id = "eleven_v3"`
   - `synthesize()` prepends inline audio tag when emotion is non-neutral
     (`[emotion] text`)
   - `synthesize()` signature does **not** include `previous_text`,
     `next_text`, or `previous_request_ids`
   - No reference to the multilingual model or any capability dict
3. The following artifacts are **deleted** outright:
   - `src/audio/tts/elevenlabs_tts_provider.py`
   - `src/audio/tts/elevenlabs_tts_provider_test.py`
   - Module constants `_MODEL_ID` and `_MODEL_CAPS` (no longer exist)
   - Helper `_caps()` (no longer exists)
4. Each new provider has its own unit test file next to the source:
   - `src/audio/tts/elevenlabs_v2_tts_provider_test.py` — covers the
     context-params path, voice-settings presets, request-id chaining, and
     `get_voices` / `get_available_voices`
   - `src/audio/tts/elevenlabs_v3_tts_provider_test.py` — covers inline-tag
     prepending, ALL-CAPS passthrough, voice-settings presets, and
     `get_voices` / `get_available_voices`
   - Neither test file monkeypatches a model-id constant; each test
     instantiates a concrete provider class.
5. Shared helper `_is_emotional(emotion)` is either duplicated in both files
   (if trivially short) or lifted into a small private module
   `src/audio/tts/_elevenlabs_common.py` shared only by the two providers.
   No re-export from a deleted location.
6. `docs/DESIGN.md` example list referencing `ElevenLabsTTSProvider`
   (`docs/DESIGN.md:20`) is updated to reference `ElevenLabsV2TTSProvider`
   (or both) — consistent with the `{Vendor}{Capability}Provider` rule
   given that the vendor now encodes model generation.
7. Any production wiring (workflows, factories, `main.py`) that previously
   referenced `ElevenLabsTTSProvider` — if and only if such references
   exist — is updated to pick one of the two new classes explicitly. As of
   this spec, no production code imports the old class; this AC is a
   placeholder covering any that appear mid-implementation.
8. All tests pass. `ruff check src/` and `mypy src/` pass.
9. `make verify` completes end-to-end without error.

## Out of Scope

- Changing the `TTSProvider` base interface.
- Changing voice-settings presets or the emotional/neutral heuristic.
- Introducing a factory or registry for TTS providers.
- Promoting the model ID to a config value (both providers hardcode theirs).
- Renaming the base `TTSProvider` or touching Fish / OpenAI providers.
- Migrating `elevenlabs_ambient_provider.py` or `elevenlabs_sound_effect_provider.py` —
  those are separate vendor surfaces and are out of scope.

## Key Design Decisions

### Why split instead of gate?

The model choice is a deploy-time decision, not a runtime one. A capability
dict is the right pattern when one class must dispatch over values that vary
within a single run — neither model-id nor its features do. The dict was
added in anticipation of supporting both models simultaneously, which never
materialised. Splitting collapses the indirection, makes the code
self-evidently correct per model, and lets each class's signature advertise
exactly the parameters that model accepts.

### Why rename `name` to `elevenlabs_v2` / `elevenlabs_v3`?

Cached audio is keyed by provider name on disk. Two providers with the same
`name` would collide caches silently — a worse footgun than the split
itself. Distinct names are cheap insurance against cross-model cache reuse.

### Why no shared base beyond `TTSProvider`?

An intermediate `_ElevenLabsBase` would re-introduce the capability gating
in parent-class form and invite future "just one more flag" additions. The
two classes share the client bootstrap (four lines) and the voice-settings
preset selection (~20 lines). Duplication is cheaper than the wrong
abstraction. If a third model appears and the duplication becomes painful,
refactor then, with evidence.

### Why delete the existing test file outright?

Every test case in `elevenlabs_tts_provider_test.py` is tied to either the
v2 or the v3 branch; splitting them requires rewriting every test's setup
(no more `monkeypatch.setattr(provider_mod, "_MODEL_ID", ...)`). Easier to
plant fresh, focused test files beside the new providers than to port.

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/audio/tts/elevenlabs_tts_provider.py` | **DELETE** |
| `src/audio/tts/elevenlabs_tts_provider_test.py` | **DELETE** |
| `src/audio/tts/elevenlabs_v2_tts_provider.py` | **CREATE** — v2 class, `name="elevenlabs_v2"`, context-params path only |
| `src/audio/tts/elevenlabs_v2_tts_provider_test.py` | **CREATE** — unit tests for v2 |
| `src/audio/tts/elevenlabs_v3_tts_provider.py` | **CREATE** — v3 class, `name="elevenlabs_v3"`, inline-tags path only |
| `src/audio/tts/elevenlabs_v3_tts_provider_test.py` | **CREATE** — unit tests for v3 |
| `src/audio/tts/_elevenlabs_common.py` | **CREATE (optional)** — `_is_emotional` if shared |
| `docs/DESIGN.md` | Update `ElevenLabsTTSProvider` example references |
| `docs/specs/index.md` | Add TD-028 row to Tech Debt table |

## Implementation Notes

- No backwards compatibility. Do not leave shims, re-exports, or
  deprecation aliases. Delete the old module cleanly in the same commit
  that introduces the replacements.
- TDD: plant failing tests for each new provider first, then write minimum
  implementations to pass them.
- After implementation, run `make verify` and confirm `output.json` is
  unchanged relative to a v2-provider run (v2 should be the default choice
  where the old class was used).
- Producers of cached audio from prior runs under `books/<id>/audio/tts/elevenlabs/`
  will no longer be found by either new provider. This is intentional —
  old caches were already ambiguous about which model produced them.
