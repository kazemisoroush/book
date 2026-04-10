# TD-016 — Add get_voices() to TTSProvider Interface

## Goal

Expose a public `get_voices()` method on the `TTSProvider` interface so
workflows can fetch available voices without reaching into provider
internals.

---

## Problem

`TTSProjectGutenbergWorkflow` (`src/workflows/tts_project_gutenberg_workflow.py:74`)
calls `provider._get_client()` to access the ElevenLabs client and fetch
voices. This is a **leaking abstraction** — the workflow breaks
encapsulation by accessing a private method, coupling itself to the
ElevenLabs implementation.

---

## Concept

Add a `get_voices()` method to the `TTSProvider` abstract interface.
Implement it in `ElevenLabsProvider` to return the list of available voices.
The workflow calls `provider.get_voices()` instead of reaching into
internals.

---

## Acceptance criteria

1. `TTSProvider` interface defines a `get_voices()` method.
2. `ElevenLabsProvider` implements `get_voices()` using its internal client.
3. `TTSProjectGutenbergWorkflow` calls `provider.get_voices()` instead of
   `provider._get_client()`.
4. No private method access (`_get_client()`) from outside the provider.
5. All existing tests continue to pass.

---

## Out of scope

- Changing how voices are designed or assigned (covered by TD-011).
- Adding voice caching or registry logic beyond the provider method.
