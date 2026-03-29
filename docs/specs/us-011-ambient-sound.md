# US-011 — Ambient Background Sound

## Goal

Layer environmental sound under the narrated audio so the listener is
placed inside the scene — a bustling café, a windswept moor, a crackling
fire, a rainy night. The AI detects the setting from the text; the
pipeline mixes the matching ambient track quietly beneath the speech.

---

## Background / motivation

Right now every scene sounds identical: voice in a silent room. A brief
passage of rain or distant crowd noise is enough to anchor the listener
in place before a word is spoken. This is standard practice in radio
drama and audiobook production.

---

## Acceptance criteria

1. A new `AmbientTag` string enum in `src/domain/models.py` with an
   initial set covering the most common literary settings:

   ```
   NONE        INDOOR       OUTDOOR
   CAFE        FOREST       RAIN
   WIND        FIRE         OCEAN
   CROWD       LIBRARY      NIGHT
   ```

2. `Chapter` gains `ambient: AmbientTag = AmbientTag.NONE`. The AI
   workflow sets it once per chapter based on the dominant scene
   setting detected in the chapter's opening sections. It does not
   change mid-chapter (ambient transitions are jarring; scene-level
   granularity is out of scope).

3. A royalty-free ambient sound library lives in
   `assets/ambient/<tag>.mp3` (one file per tag, loopable, at least
   30 s long). `NONE` has no file. The files are not committed to git
   (added to `.gitignore`); a `make assets` target downloads them from
   a documented public source.

4. `TTSOrchestrator.synthesize_chapter()` receives `chapter.ambient`.
   When not `NONE`, after stitching the chapter speech audio it uses
   ffmpeg to mix the ambient track (looped to match chapter length) at
   −18 dB beneath the speech. Output is still a single
   `chapter_NN.mp3`.

5. `make verify` produces `output.json` with an `ambient` field on
   each chapter.

6. New unit tests cover:
   - `Chapter` round-trips `ambient` through `to_dict` / `from_dict`
   - ffmpeg mix command is constructed correctly for a known ambient tag
     (mock ffmpeg call — 1 mock)

---

## Out of scope

- Per-section ambient changes within a chapter
- Custom ambient file upload
- Ambient on dialogue segments only (ambient runs across the full chapter)
- Spatial / stereo positioning

---

## Key design decisions

### One ambient per chapter, not per section
Cutting between ambient tracks mid-chapter is disorienting. The chapter
is the right granularity: the AI sets the dominant setting once and it
holds for the full chapter runtime.

### Assets not in git
Audio files are large binaries. A `make assets` download script keeps
the repo lightweight and makes the source of each file auditable.

### −18 dB default mix level
Speech intelligibility drops sharply if ambient is above −20 dB relative
to speech. −18 dB is audible but unobtrusive. A future spec can make
this configurable.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `AmbientTag` enum; add `ambient` field to `Chapter` |
| `src/workflows/ai_project_gutenberg_workflow.py` | Detect and set `chapter.ambient` |
| `src/tts/tts_orchestrator.py` | Mix ambient after stitch |
| `assets/ambient/` | Royalty-free ambient MP3s (gitignored) |
| `Makefile` | Add `make assets` download target |
