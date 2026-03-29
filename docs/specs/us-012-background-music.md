# US-012 — Background Music

## Goal

Underscore scenes with royalty-free music that matches the emotional
arc of the moment — a tense string piece as danger approaches, a gentle
piano as a character grieves, an upbeat theme for a comedic exchange.
Music makes the listener _feel_ the story, not just hear it.

---

## Background / motivation

Ambient sound (US-011) places the listener in a physical space.
Background music does something different: it primes the emotional
response before the words arrive, the same way a film score does. A
well-chosen 30-second loop under a sad scene amplifies the impact of the
prose far beyond what voice alone achieves.

---

## Acceptance criteria

1. A new `MusicMood` string enum in `src/domain/models.py`:

   ```
   NONE        NEUTRAL     DRAMATIC
   SAD         HAPPY       TENSE
   ROMANTIC    MYSTERIOUS  COMEDIC
   TRIUMPHANT
   ```

2. `Chapter` gains `music_mood: MusicMood = MusicMood.NONE`. The AI
   workflow sets it once per chapter based on the dominant emotional
   arc of the chapter. `NONE` means no music track is mixed in.

3. A royalty-free music library lives in `assets/music/<mood>.mp3`
   (one track per mood, loopable, at least 60 s). Files are gitignored;
   `make assets` downloads them from a documented public source (e.g.
   Free Music Archive, ccMixter, or similar CC-licensed source).

4. `TTSOrchestrator.synthesize_chapter()` receives `chapter.music_mood`.
   When not `NONE`, after stitching the chapter speech audio it uses
   ffmpeg to mix the music track (looped to chapter length) at −22 dB
   beneath speech. Music is mixed _after_ ambient (if US-011 is active)
   so all three layers — speech, ambient, music — are combined in one
   ffmpeg pass.

5. Music fades in over the first 3 s and fades out over the last 3 s of
   the chapter to avoid hard cuts. ffmpeg `afade` filter handles this.

6. `make verify` produces `output.json` with a `music_mood` field on
   each chapter.

7. New unit tests cover:
   - `Chapter` round-trips `music_mood` through `to_dict` / `from_dict`
   - ffmpeg command includes `afade` in/out when music mood is non-NONE
     (mock ffmpeg — 1 mock)

---

## Out of scope

- Per-section music changes (chapter granularity only)
- Dynamic tempo or key matching to speech pace
- Music licensing verification (caller's responsibility)
- Music mixed with ambient from US-011 is in scope; but US-011 is not
  a hard dependency — US-012 can ship independently

---

## Key design decisions

### −22 dB for music vs −18 dB for ambient
Music has melody and rhythm — it competes more with speech attention
than ambient noise does. A lower mix level keeps it subliminal rather
than distracting. The 4 dB gap between ambient and music maintains the
hierarchy: speech > ambient > music.

### Mood detected per chapter, not per segment
Scene-level mood changes are common; sentence-level changes would
produce a jarring experience of constant music cuts. Chapter is the
right granularity for the first version.

### One track per mood, not a playlist
A single loopable track per mood is simple to implement and test. A
playlist / shuffle feature is a natural follow-up but out of scope here.

### 3 s fade in/out
Hard music cuts at chapter boundaries are jarring. A 3 s fade is
imperceptible to the listener but eliminates the click. ffmpeg's
`afade` handles this in one filter argument.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `MusicMood` enum; add `music_mood` field to `Chapter` |
| `src/workflows/ai_project_gutenberg_workflow.py` | Detect and set `chapter.music_mood` |
| `src/tts/tts_orchestrator.py` | Mix music with fade after stitch |
| `assets/music/` | Royalty-free mood MP3s (gitignored) |
| `Makefile` | `make assets` updated to download music tracks |
