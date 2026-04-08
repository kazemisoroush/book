# TD-014 — Break Circular TTSOrchestrator Imports

## Goal

Eliminate the circular coupling where `SegmentSynthesizer` and
`AudioAssembler` import `TTSOrchestrator` to read class constants.
Inject feature flags at construction instead.

---

## Problem

`SegmentSynthesizer` (`src/tts/segment_synthesizer.py:52-54`) and
`AudioAssembler` (`src/tts/audio_assembler.py:58`) both import
`TTSOrchestrator` inside their methods to access class-level constants.
This is a **dependency inversion violation** — lower-level components reach
up to their orchestrator, creating circular coupling.

---

## Concept

Move the shared constants (feature flags / configuration values) out of
`TTSOrchestrator` and into constructor parameters on `SegmentSynthesizer`
and `AudioAssembler`. The orchestrator passes the values down at
construction time. No component imports its parent.

This pairs with the `FeatureFlags` config object that already exists in the
project — use it or extend it to carry these values.

---

## Acceptance criteria

1. `SegmentSynthesizer` does not import `TTSOrchestrator`.
2. `AudioAssembler` does not import `TTSOrchestrator`.
3. Both receive the values they need via constructor injection.
4. `TTSOrchestrator` passes the values when constructing its collaborators.
5. All existing tests continue to pass.
6. No circular import paths remain in the `tts/` package.

---

## Out of scope

- Refactoring `TTSOrchestrator` beyond removing the constants that cause
  circular imports.
- Changing TTS synthesis behaviour.
