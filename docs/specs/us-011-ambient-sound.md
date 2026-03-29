# US-011 — Ambient Background Sound

## Goal

Layer environmental sound under the narrated audio so the listener is
placed inside the scene — a bustling café, a windswept moor, a crackling
fire, a rainy night. The AI detects the setting from the text; the
pipeline generates and mixes a matching ambient track quietly beneath
the speech using the ElevenLabs Sound Effects API.

---

## Background / motivation

Right now every scene sounds identical: voice in a silent room. A brief
passage of rain or distant crowd noise is enough to anchor the listener
in place before a word is spoken. This is standard practice in radio
drama and audiobook production.

The ElevenLabs Sound Effects API (`POST /v1/sound-generation`) generates
loopable audio from a text description. This removes any dependency on
static asset files and keeps the repository lightweight while producing
ambient sounds that are matched to each scene's character.

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

3. A `src/tts/ambient_generator.py` module exposes:

   ```python
   def get_ambient_audio(tag: AmbientTag, output_dir: Path, client: ElevenLabs) -> Path:
       """Return path to an ambient MP3 for the given tag.

       Generates via ElevenLabs Sound Effects API on first call;
       caches the result in output_dir/ambient/<tag>.mp3 for subsequent calls.
       Returns the path to the cached file.
       """
   ```

   Prompt used for generation (one per tag, hard-coded in the module):

   | Tag      | Prompt                                              |
   |----------|-----------------------------------------------------|
   | INDOOR   | soft indoor ambience, quiet room tone               |
   | OUTDOOR  | gentle outdoor ambience, light breeze               |
   | CAFE     | busy café, coffee shop background noise, murmur     |
   | FOREST   | forest ambience, birds, rustling leaves, breeze     |
   | RAIN     | steady rain on a window, light rainfall             |
   | WIND     | howling wind, blustery outdoor wind                 |
   | FIRE     | crackling fireplace, wood burning                   |
   | OCEAN    | ocean waves, sea shore, gentle surf                 |
   | CROWD    | crowd noise, busy street, marketplace               |
   | LIBRARY  | library ambience, quiet, occasional page turn       |
   | NIGHT    | night ambience, crickets, distant owl               |

   The API call uses `duration_seconds=60` to generate a loopable clip.

4. `TTSOrchestrator.synthesize_chapter()` receives `chapter.ambient`.
   When not `NONE`, after stitching the chapter speech audio it calls
   `get_ambient_audio()` to obtain the track, then uses ffmpeg to mix it
   (looped to match chapter length) at −18 dB beneath the speech.
   Output is still a single `chapter_NN.mp3`.

5. `make verify` produces `output.json` with an `ambient` field on
   each chapter.

6. New unit tests cover:
   - `Chapter` round-trips `ambient` through `to_dict` / `from_dict`
   - ffmpeg mix command is constructed correctly for a known ambient tag
     (mock `get_ambient_audio` — 1 mock)

---

## Out of scope

- Per-section ambient changes within a chapter
- Custom ambient file upload
- Ambient on dialogue segments only (ambient runs across the full chapter)
- Spatial / stereo positioning
- Re-generating cached ambient files (delete cache to regenerate)

---

## Key design decisions

### ElevenLabs Sound Effects API instead of static assets
Generating audio on demand removes the need to commit or download binary
asset files. The cache-on-disk pattern ensures each tag is generated at
most once per output directory. If the API is unavailable, the chapter
is produced without ambient (logged as a warning, not an error).

### One ambient per chapter, not per section
Cutting between ambient tracks mid-chapter is disorienting. The chapter
is the right granularity: the AI sets the dominant setting once and it
holds for the full chapter runtime.

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
| `src/tts/ambient_generator.py` | New module — generate and cache ambient audio |
| `src/tts/tts_orchestrator.py` | Mix ambient after stitch |
