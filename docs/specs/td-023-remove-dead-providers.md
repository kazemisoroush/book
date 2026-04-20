# TD-023 — Remove Dead Providers

## Problem

OpenAI TTS and Stable Audio (ambient + SFX) providers are unused but still
imported by production workflows. They add dead code, stale env-var
requirements (`STABILITY_API_KEY`), and confusion about what's actually wired.

## Proposed Solution

Delete OpenAI TTS and Stable Audio providers (ambient + SFX) and their tests.
Rewire workflows to use ElevenLabs for ambient and SFX. Remove
`stability_api_key` from `Config`. Keep Suno Music — it's still viable.
