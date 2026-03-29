# US-012 — Background Music

## Goal

Underscore scenes with generative music that matches the emotional
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

The ElevenLabs Music API (`POST /v1/audio/music`) generates music from a
text prompt. This removes any dependency on static royalty-free tracks and
allows the music to be described precisely for each mood — no licensing
concerns, no external downloads.

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

3. A `src/tts/music_generator.py` module exposes:

   ```python
   def get_music_audio(mood: MusicMood, output_dir: Path, client: ElevenLabs) -> Path:
       """Return path to a music MP3 for the given mood.

       Generates via ElevenLabs Music API on first call;
       caches the result in output_dir/music/<mood>.mp3 for subsequent calls.
       Returns the path to the cached file.
       """
   ```

   Prompt used for generation (one per mood, hard-coded in the module):

   | Mood        | Prompt                                                        |
   |-------------|---------------------------------------------------------------|
   | NEUTRAL     | calm neutral background music, subtle, unobtrusive           |
   | DRAMATIC    | dramatic orchestral score, building tension, cinematic        |
   | SAD         | melancholic piano, soft, sorrowful, slow tempo               |
   | HAPPY       | uplifting light music, cheerful, warm, positive              |
   | TENSE       | tense suspenseful strings, low pulse, thriller score          |
   | ROMANTIC    | romantic strings, tender, gentle waltz feel                   |
   | MYSTERIOUS  | mysterious ambient music, dark undertones, eerie              |
   | COMEDIC     | playful comedy music, light, whimsical, bouncy               |
   | TRIUMPHANT  | triumphant fanfare, heroic brass, victorious, energetic       |

   The API call uses a duration that yields at least 60 s of audio.

4. `TTSOrchestrator.synthesize_chapter()` receives `chapter.music_mood`.
   When not `NONE`, after stitching the chapter speech audio (and after
   applying ambient from US-011 if active), it calls `get_music_audio()`
   to obtain the track, then uses ffmpeg to mix it (looped to chapter
   length) at −22 dB beneath speech. Music is mixed _after_ ambient so
   all three layers — speech, ambient, music — are combined in one
   ffmpeg pass.

5. Music fades in over the first 3 s and fades out over the last 3 s of
   the chapter to avoid hard cuts. ffmpeg `afade` filter handles this.

6. `make verify` produces `output.json` with a `music_mood` field on
   each chapter.

7. New unit tests cover:
   - `Chapter` round-trips `music_mood` through `to_dict` / `from_dict`
   - ffmpeg command includes `afade` in/out when music mood is non-NONE
     (mock `get_music_audio` — 1 mock)

---

## Out of scope

- Per-section music changes (chapter granularity only)
- Dynamic tempo or key matching to speech pace
- Re-generating cached music files (delete cache to regenerate)
- Music mixed with ambient from US-011 is in scope; but US-011 is not
  a hard dependency — US-012 can ship independently

---

## Key design decisions

### ElevenLabs Music API instead of static royalty-free tracks
Generating music on demand removes licensing concerns entirely and
allows mood-specific prompts rather than relying on a curated library.
The cache-on-disk pattern ensures each mood is generated at most once
per output directory.

### −22 dB for music vs −18 dB for ambient
Music has melody and rhythm — it competes more with speech attention
than ambient noise does. A lower mix level keeps it subliminal rather
than distracting. The 4 dB gap between ambient and music maintains the
hierarchy: speech > ambient > music.

### Mood detected per chapter, not per segment
Scene-level mood changes are common; sentence-level changes would
produce a jarring experience of constant music cuts. Chapter is the
right granularity for the first version.

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
| `src/tts/music_generator.py` | New module — generate and cache music audio |
| `src/tts/tts_orchestrator.py` | Mix music with fade after stitch |
