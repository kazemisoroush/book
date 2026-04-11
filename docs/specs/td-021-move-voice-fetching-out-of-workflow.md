# TD-021 — Move Voice Fetching Out of Workflow

## Goal

Remove voice fetching logic from `TTSProjectGutenbergWorkflow.create()` and move
it into `VoiceAssigner`, so the workflow no longer needs to know about
`VoiceEntry` objects. The workflow becomes a pure orchestrator; `VoiceAssigner`
owns all voice-related concerns.

---

## Problem

`TTSProjectGutenbergWorkflow.create()` (`src/workflows/tts_project_gutenberg_workflow.py:92-101`)
calls `tts_provider.get_voices()` and manually wraps each voice in a `VoiceEntry`
object. It then stores the list as `voice_entries` on the workflow instance and
passes it to `VoiceAssigner` in `run()` (line 198).

This violates single responsibility:
- The workflow should orchestrate high-level steps (download, parse, assign, synthesise)
- `VoiceAssigner` should own all concerns related to voices: fetching, wrapping, assigning

Furthermore, the workflow is forced to import `VoiceEntry` at the module level
(line 16), coupling itself to an internal TTS data structure.

**Test impact**: `VoiceAssigner` has 14+ test call sites that construct
`VoiceEntry` lists directly. Adding a mock for `TTSProvider` (to fetch voices
inside `assign()`) would create a second mock per test, violating the 1-mock
rule. This design debt must be addressed at the same time.

---

## Concept

### Phase 1: Decouple VoiceAssigner from Concrete VoiceEntry Lists

Refactor `VoiceAssigner` to accept a `TTSProvider` instead of a pre-built
`list[VoiceEntry]`. The assigner calls `get_voices()` internally and wraps
the results.

Since tests need to supply pre-built `VoiceEntry` lists without calling a real
provider, add a **test helper class** `StubTTSProvider` that accepts a
`list[VoiceEntry]` and returns them directly from `get_voices()`. This keeps
tests simple: tests construct voices, pass them to the stub, and the stub
appears as a `TTSProvider` to `VoiceAssigner`. No mock needed.

```python
# Example test usage (after refactor)
voices = [VoiceEntry(...), VoiceEntry(...)]
stub_provider = StubTTSProvider(voices)
assigner = VoiceAssigner(stub_provider)  # No mock!
assignment = assigner.assign(registry)
```

### Phase 2: Update Workflow to Pass Provider Directly

`TTSProjectGutenbergWorkflow.run()` calls `VoiceAssigner(provider)` instead of
`VoiceAssigner(voice_entries)`. The assigner handles voice fetching.

```python
# Old
voice_entries = [VoiceEntry(...) for v in tts_provider.get_voices()]
assigner = VoiceAssigner(voice_entries)

# New
assigner = VoiceAssigner(tts_provider)
```

The workflow no longer imports or constructs `VoiceEntry` at all.

---

## Acceptance criteria

1. `VoiceAssigner.__init__()` accepts a `TTSProvider` instead of
   `list[VoiceEntry]`.

2. `VoiceAssigner` calls `provider.get_voices()` in `__init__()` and wraps each
   result in a `VoiceEntry` internally. The wrapping logic is identical to
   what the workflow currently does (lines 94-101).

3. `VoiceAssigner` stores the wrapped voices as `_voice_entries` (private).
   The public API (`assign()` method) remains unchanged.

4. A new `StubTTSProvider` class is added to `src/tts/tts_provider.py`:
   - Implements the `TTSProvider` abstract interface
   - Accepts a `list[VoiceEntry]` at construction
   - Returns those voices directly from `get_voices()`
   - Raises `NotImplementedError` for other methods (`synthesize`,
     `get_available_voices`)
   - Is located in the same module as the `TTSProvider` ABC so tests can
     import it without creating a new module

5. All existing tests in `src/tts/voice_assigner_test.py` continue to pass.
   Tests are updated to use `StubTTSProvider` instead of constructing
   `VoiceEntry` lists directly and passing them to `VoiceAssigner`.
   **No mocks are added to any test.**

6. `TTSProjectGutenbergWorkflow.__init__()` and `create()` are updated:
   - Remove `voice_entries` parameter from `__init__()`
   - Remove voice fetching logic from `create()`
   - Store only the `tts_provider`

7. `TTSProjectGutenbergWorkflow.run()` constructs `VoiceAssigner(self._tts_provider)`
   instead of `VoiceAssigner(self._voice_entries)`.

8. No imports of `VoiceEntry` remain in `tts_project_gutenberg_workflow.py`.

9. All workflow tests continue to pass.

10. No provider method outside of `TTSProjectGutenbergWorkflow` calls
    `get_voices()` directly — all voice fetching is now internal to
    `VoiceAssigner`.

---

## Out of scope

- Changing the voice assignment algorithm or `assign()` signature
- Adding voice caching or persistence
- Changing how `FeatureFlags` or other configuration is passed
- Refactoring other workflows or providers
- Changing TTS synthesis behaviour
- Adding new feature flags or config fields

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/tts_provider.py` | Add `StubTTSProvider` class implementing `TTSProvider` |
| `src/tts/voice_assigner.py` | Update `__init__()` to accept `TTSProvider` instead of `list[VoiceEntry]`; add internal wrapping logic |
| `src/tts/voice_assigner_test.py` | Update all 14+ tests to use `StubTTSProvider` instead of direct `VoiceEntry` list construction; no mocks added |
| `src/workflows/tts_project_gutenberg_workflow.py` | Remove `voice_entries` parameter; remove voice fetching in `create()`; pass `tts_provider` to `VoiceAssigner` in `run()` |

---

## Relationship to other specs

- **TD-016** (Add get_voices to TTSProvider Interface): Established the
  `get_voices()` method that this spec now moves into `VoiceAssigner`
- **US-024** (Audio Provider Interface Separation): Defines the `TTSProvider`
  ABC that `VoiceAssigner` will now depend on

---

## Key design decisions

### Why a `StubTTSProvider` instead of mocking?

The 1-mock-per-test rule is strict (see CLAUDE.md). Tests for `VoiceAssigner`
have many call sites (14+) and would need both a mock for `TTSProvider` AND a
mock for `voice_registry` (already used in voice design tests). This violates
the rule.

By creating a deterministic `StubTTSProvider` that returns pre-built voices,
tests avoid mocking and stay simple:

```python
# Good — no mock
voices = [VoiceEntry(...), ...]
stub = StubTTSProvider(voices)
assigner = VoiceAssigner(stub)
assignment = assigner.assign(registry)

# Bad — 2 mocks (violates rule)
provider_mock = MagicMock()
registry_mock = MagicMock()
assigner = VoiceAssigner(provider_mock)
assigner.assign(registry_mock)
```

### Why wrap voices in `__init__()` instead of `assign()`?

Wrapping at construction time is deterministic and matches the old workflow
behaviour. It also simplifies `assign()` — the method works with pre-built
`VoiceEntry` objects without having to manage fetching.

### Why keep `_voice_entries` private?

The `VoiceEntry` type is an implementation detail of `VoiceAssigner`. Callers
should only care about the `assign()` method and its output (`dict[str, str]`).
Keeping `_voice_entries` private enforces this boundary.

---

## Implementation notes

1. When wrapping voices in `VoiceAssigner.__init__()`, use the same logic that
   currently lives in `TTSProjectGutenbergWorkflow.create()` (lines 94-101):
   ```python
   raw_voices = self._provider.get_voices()
   self._voice_entries = [
       VoiceEntry(
           voice_id=v["voice_id"],
           name=v["name"],
           labels=v.get("labels", {}),
       )
       for v in raw_voices
   ]
   ```

2. If `get_voices()` returns an empty list, raise `ValueError` with a clear
   message (matching current workflow behaviour at line 102-103).

3. The `StubTTSProvider` may live at the end of `tts_provider.py` after the
   abstract interface. It is meant to be a test helper and should be imported
   by test files (e.g., `from src.tts.tts_provider import StubTTSProvider`).

4. All voice fetching errors (API failures, network issues) are now the
   responsibility of the provider's `get_voices()` implementation. `VoiceAssigner`
   simply propagates them.

5. The workflow should continue to accept a `books_dir` parameter and create
   provider instances appropriately. This spec touches only `VoiceAssigner`
   construction in `run()` — no changes to provider instantiation logic.
