# TD-019 — Wire New Providers into Workflow

## Goal

Hard-code the new audio providers into the workflow: Fish Audio for TTS,
Stable Audio for ambient sound, Suno AI for music. No config-driven provider
selection, no builder pattern — just static wiring.

---

## Problem

US-025, US-026, US-027, and US-028 each deliver standalone provider
implementations with tests, but none of them touch `config.py` or the
workflow. Without wiring, the new providers exist as dead code — importable
but never instantiated by the pipeline.

---

## Acceptance criteria

1. `src/config/config.py` gains new optional API key fields:
   - `fish_audio_api_key: Optional[str]` — loaded from `FISH_AUDIO_API_KEY`
   - `stability_api_key: Optional[str]` — loaded from `STABILITY_API_KEY`
   - `suno_api_key: Optional[str]` — loaded from `SUNO_API_KEY`

2. `src/workflows/tts_project_gutenberg_workflow.py` hard-codes provider
   instantiation:
   - **TTS**: `FishAudioTTSProvider`
   - **Ambient sound**: `StableAudioAmbientProvider`
   - **Music**: `SunoMusicProvider`

3. No provider selection fields, no enums, no factory functions, no fallback
   wrapping. The workflow imports the concrete classes and instantiates them
   directly.

4. All existing tests continue to pass.

5. New tests cover:
   - Config loading for each new API key field
   - Workflow instantiates the correct concrete provider classes

---

## Out of scope

- Provider selection via config/env vars (no `tts_provider` field, no enums)
- Builder pattern or factory functions
- Fallback wrapping (`FallbackTTSProvider`)
- OpenAI TTS provider wiring (not used in this workflow)
- UI or CLI flags for provider selection
- Provider health checks or automatic failover
- Per-chapter or per-character provider selection
- Cost tracking or quota management

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/config/config.py` | Add API key fields for Fish Audio, Stability, Suno |
| `src/workflows/tts_project_gutenberg_workflow.py` | Import and instantiate Fish Audio, Stable Audio, Suno directly |

---

## Relationship to other specs

- **US-025 (Fish Audio)**: Provides `FishAudioTTSProvider` class
- **US-027 (Stable Audio)**: Provides `StableAudioAmbientProvider`
- **US-028 (Suno Music)**: Provides `SunoMusicProvider`
- **US-024 (Interface Separation)**: Defines the provider ABCs used for type hints

---

## Prerequisites

US-025, US-027, and US-028 must be completed before this spec can be
implemented. Each delivers a standalone provider; this spec wires them
into the workflow.
