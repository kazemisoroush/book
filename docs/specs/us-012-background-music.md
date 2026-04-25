# US-012 — Background Music

## Problem

Audiobooks rely on voice alone to convey emotion. Film and television use music
to prime emotional response before dialogue begins. The pipeline has no
mechanism for music — no representation in the domain model, no AI detection,
no generation or mixing pipeline.

## Proposed Solution

Add `MUSIC = "music"` to `BeatType`. The AI parser detects moments where
background music should start and emits MUSIC beats with free-form text
descriptions (e.g. "tense orchestral strings building slowly"). Music continues
until the next MUSIC beat replaces it, a `"silence"` MUSIC beat ends it,
or the chapter ends.

The `AudioOrchestrator` skips MUSIC beats during TTS synthesis (they're
timeline markers, not spoken text). After stitching speech, it calls
`MusicProvider.generate()` for each MUSIC beat, then mixes the result under
speech at -22 dB with 3s fade-in/out via ffmpeg.

Gated by `music_enabled` feature flag (default off).
