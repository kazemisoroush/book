# US-016 — Inter-Segment Silence

## Goal

Insert a configurable silence gap between consecutive TTS segments when
stitching audio, so the assembled chapter breathes naturally instead of
running words together at segment boundaries.

---

## Background / motivation

Segments are currently concatenated with ffmpeg using a plain `concat`
filter and no gap. The result is that speaker transitions and
narration-to-dialogue switches feel abrupt — the audio jumps from one
voice to the next with no pause. A short silence (200–500 ms) at each
boundary significantly improves perceived naturalness.

There are two meaningfully different boundary types that warrant different
gap lengths:

- **Same-speaker boundary** (narration block continues, or the same
  character speaks in two adjacent segments): short gap (~150 ms).
- **Speaker-change boundary** (narrator → character, character → narrator,
  or character A → character B): longer gap (~400 ms).

---

## Acceptance criteria

1. `AudioOrchestrator` gains a `silence_same_speaker_ms: int = 150` and
   `silence_speaker_change_ms: int = 400` parameter (both with defaults).

2. When building the ffmpeg concat list, a generated silent `.mp3` clip of
   the appropriate duration is inserted between every pair of consecutive
   segments.

3. The silence clip is generated once per unique duration using
   `ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t <seconds> -q:a 9
   -acodec libmp3lame <path>` and reused for all boundaries of the same
   duration within a chapter.

4. Segment boundary type is determined by comparing `segment.character_id`
   of adjacent segments:
   - Same `character_id` → `silence_same_speaker_ms`
   - Different `character_id` → `silence_speaker_change_ms`

5. The `_stitch_with_ffmpeg` method signature and call sites are updated
   to accept the segment list (needed to determine boundary types).

6. Unit tests cover:
   - Same-speaker boundary uses short silence duration.
   - Speaker-change boundary uses long silence duration.
   - Silence clips are inserted between every pair (N segments → N-1 gaps).
   - Single-segment chapter produces no silence clip.

---

## Out of scope

- Silence after the final segment.
- Per-emotion gap tuning.
- Silence within a segment (see US-017).

---

## Key design decisions

### Generate silence via ffmpeg, not a bundled asset
Generating silence programmatically keeps the repo free of binary assets
and makes the duration trivially configurable. The `anullsrc` lavfi source
is available in all standard ffmpeg builds.

### Two gap sizes, not one
A flat gap sounds mechanical. Differentiating by speaker change is the
minimum needed to feel natural without requiring per-segment tuning.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/audio_orchestrator.py` | Add silence params; generate silence clips; insert in concat list |
| `src/tts/audio_orchestrator_test.py` | Tests for gap insertion logic |
