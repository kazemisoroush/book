# TD-019 — Wire New Providers into Workflow

## Goal

Add config fields for new provider API keys and wire provider selection into
the workflow so users can choose which TTS, SFX, ambient, and music providers
to use.

---

## Problem

US-025, US-026, US-027, and US-028 each deliver standalone provider
implementations with tests, but none of them touch `config.py` or the
workflow. Without wiring, the new providers exist as dead code — importable
but never instantiated by the pipeline.

---

## Acceptance criteria

1. `src/config/config.py` gains new optional fields:
   - `fish_audio_api_key: Optional[str]` — loaded from `FISH_AUDIO_API_KEY`
   - `openai_api_key: Optional[str]` — loaded from `OPENAI_API_KEY`
   - `stability_api_key: Optional[str]` — loaded from `STABILITY_API_KEY`
   - `suno_api_key: Optional[str]` — loaded from `SUNO_API_KEY`

2. `src/config/config.py` gains provider selection fields:
   - `tts_provider: str = "elevenlabs"` — one of `elevenlabs`, `fish_audio`, `openai`
   - `sfx_provider: str = "elevenlabs"` — one of `elevenlabs`, `stable_audio`
   - `ambient_provider: str = "elevenlabs"` — one of `elevenlabs`, `stable_audio`
   - `music_provider: Optional[str] = None` — one of `suno`, `None`

3. `src/workflows/tts_project_gutenberg_workflow.py` reads provider selection
   from config and instantiates the correct provider class. Falls back to
   ElevenLabs if the selected provider's API key is missing.

4. When `tts_provider` is set and a `fallback_tts_provider` field is also set,
   the workflow wraps both in `FallbackTTSProvider`.

5. All existing tests continue to pass (default config = ElevenLabs everywhere).

6. New tests cover:
   - Config loading for each new API key field
   - Provider instantiation for each selection value
   - Fallback wrapping when both primary and fallback are configured
   - Graceful default when selected provider's key is missing

---

## Out of scope

- UI or CLI flags for provider selection (config/env vars only)
- Provider health checks or automatic failover beyond `FallbackTTSProvider`
- Per-chapter or per-character provider selection
- Cost tracking or quota management

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/config/config.py` | Add API key fields and provider selection fields |
| `src/workflows/tts_project_gutenberg_workflow.py` | Provider instantiation logic |

---

## Relationship to other specs

- **US-025 (Fish Audio)**: Provides `FishAudioTTSProvider` class
- **US-026 (OpenAI TTS)**: Provides `OpenAITTSProvider` and `FallbackTTSProvider`
- **US-027 (Stable Audio)**: Provides `StableAudioSoundEffectProvider` and `StableAudioAmbientProvider`
- **US-028 (Suno Music)**: Provides `SunoMusicProvider`
- **US-024 (Interface Separation)**: Defines the provider ABCs used for type hints

---

## Prerequisites

All of US-025, US-026, US-027, US-028 must be completed before this spec
can be implemented. Each delivers a standalone provider; this spec wires
them together.
