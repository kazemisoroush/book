# TD-015 — Replace TTSOrchestrator Class Constants with Feature Flags

## Goal

Replace hardcoded class constants in `TTSOrchestrator` with a `FeatureFlags`
instance passed at construction, so behaviour can be configured without
modifying the class.

---

## Problem

`TTSOrchestrator` (`src/tts/tts_orchestrator.py:206-217`) uses class-level
constants as feature flags. Changing behaviour requires editing the class
source — an **Open/Closed violation**. These constants are also the root
cause of the circular imports in TD-014.

---

## Concept

Accept a `FeatureFlags` instance (from `src/config/feature_flags.py`) in the
`TTSOrchestrator` constructor. Read flag values from it instead of class
constants. This allows runtime configuration and eliminates the need for
other modules to import the orchestrator just to read flags.

---

## Acceptance criteria

1. `TTSOrchestrator` accepts a `FeatureFlags` instance at construction.
2. All class-level feature constants are read from the flags object.
3. Behaviour is unchanged with default flag values.
4. New flags can be added without modifying `TTSOrchestrator` source.
5. All existing tests continue to pass.

---

## Out of scope

- Adding new feature flags beyond what currently exists as class constants.
- Changing the `FeatureFlags` persistence format.
