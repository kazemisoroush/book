# US-012 — Background Music

## Problem

Audiobooks rely on voice alone to convey emotion. Film and television use music
to prime emotional response before dialogue begins. The pipeline has no
mechanism for music — no representation in the domain model, no AI detection,
no generation or mixing pipeline.

## Proposed Solution

Add `MUSIC = "music"` to `SegmentType`. The AI parser detects moments where
background music should start and emits MUSIC segments with free-form text
descriptions (e.g. "tense orchestral strings building slowly"). Music continues
until the next MUSIC segment replaces it, a `"silence"` MUSIC segment ends it,
or the chapter ends.

The `AudioOrchestrator` skips MUSIC segments during TTS synthesis (they're
timeline markers, not spoken text). After stitching speech, it calls
`MusicProvider.generate()` for each MUSIC segment, then mixes the result under
speech at -22 dB with 3s fade-in/out via ffmpeg.

Gated by `music_enabled` feature flag (default off).
