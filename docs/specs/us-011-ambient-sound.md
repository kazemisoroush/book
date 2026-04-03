# US-011 — Ambient Background Sound

## Goal

Layer environmental sound under the narrated audio so the listener is
placed inside the scene — a bustling café, a windswept moor, a crackling
fire, a rainy night. Ambient sound is **per-scene** (not per-chapter),
generated from LLM-provided descriptions via the ElevenLabs Sound Effects
API, and cross-faded at scene boundaries.

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

### Relationship to US-020

US-020 (shipped) introduced `SceneRegistry` with per-segment `scene_id`,
`environment`, `acoustic_hints`, and `voice_modifiers`. US-011 extends
`Scene` with ambient-specific fields and adds audio generation + mixing.
No new detection mechanism is needed — ambient metadata rides on the
existing scene detection pipeline.

---

## Acceptance criteria

1. `Scene` gains two optional fields in `src/domain/models.py`:
   - `ambient_prompt: Optional[str]` — natural-language description of
     the ambient sound (e.g., `"quiet drawing room, clock ticking,
     distant servant footsteps"`). When `None`, no ambient is generated
     for that scene.
   - `ambient_volume: Optional[float]` — mix level in dB relative to
     speech (e.g., `-18.0`, `-20.0`). The AI provides this per scene:
     quieter for intimate settings, louder for battlefields.

2. The AI parser provides `ambient_prompt` and `ambient_volume` as part
   of the scene response (same call that already detects
   `environment` / `acoustic_hints` / `voice_modifiers`). No separate
   detection step.

3. A new `src/tts/ambient_generator.py` module exposes:

   ```python
   def get_ambient_audio(
       scene: Scene,
       output_dir: Path,
       client: ElevenLabs,
   ) -> Optional[Path]:
       """Return path to an ambient MP3 for the given scene.

       Generates via ElevenLabs Sound Effects API using scene.ambient_prompt
       on first call; caches the result in output_dir/ambient/{scene_id}.mp3
       for subsequent calls. Returns None if ambient_prompt is None or if
       the API call fails (logged as warning, not error).
       """
   ```

   The API call uses `duration_seconds=60` to generate a loopable clip.

4. `TTSOrchestrator.synthesize_chapter()` determines which scenes appear
   in the chapter and their segment ranges. For each scene with ambient:
   - Calls `get_ambient_audio()` to obtain (or cache-hit) the track
   - Loops the 60 s clip to cover the scene's duration
   - Mixes at the scene's `ambient_volume` dB level
   - Applies a **5-second cross-fade** between adjacent scenes at
     scene boundaries
   - Output remains a single `chapter_NN.mp3`

5. `make verify` produces `output.json` with `ambient_prompt` and
   `ambient_volume` on each scene in the `scene_registry`.

6. When all segments in a chapter have `ambient_prompt = None` (or no
   scene), the chapter is produced identically to today (no regression).

7. On API failure, the chapter is produced without ambient for the
   affected scene. A warning is logged but it is not a hard error.

8. New unit tests cover:
   - `Scene` round-trips `ambient_prompt` and `ambient_volume` through
     `to_dict` / `from_dict`
   - ffmpeg mix command is constructed correctly for a scene with ambient
     (mock `get_ambient_audio` — 1 mock)
   - Cross-fade ffmpeg filter is constructed correctly at scene boundaries
   - No ambient path: chapter produced without ambient audio

---

## Out of scope

- Custom ambient file upload
- Spatial / stereo positioning
- Re-generating cached ambient files (delete cache to regenerate)
- Ambient volume normalization across chapters
- Background music (this is environmental sound only)

---

## Key design decisions

### Per-scene ambient, not per-chapter

The original US-011 spec assumed one ambient per chapter. Since US-020
introduced per-segment scene tracking via `SceneRegistry`, ambient now
follows scenes. A chapter that moves from a drawing room to a ball gets
different ambient for each. Scene boundaries use a 5-second cross-fade
to avoid jarring cuts.

### LLM-provided ambient descriptions, not a static enum

The original spec used a hard-coded `AmbientTag` enum with fixed prompts.
This follows the same pattern as US-019 Fix 3 (LLM-provided voice settings)
and US-020 (LLM-provided voice modifiers): the AI provides contextually
appropriate descriptions like `"quiet drawing room, clock ticking, distant
servant footsteps"` rather than mapping through a generic `INDOOR` tag.
This produces ambient sound that matches the specific narrative moment.

### LLM-provided ambient volume

Rather than a fixed −18 dB for all scenes, the AI provides `ambient_volume`
per scene. Intimate settings get quieter ambient (e.g., −20 dB), busy
environments get louder (e.g., −16 dB). This keeps speech intelligible
while matching the scene's energy.

### ElevenLabs Sound Effects API instead of static assets

Generating audio on demand removes the need to commit or download binary
asset files. The cache-by-`scene_id` pattern ensures each scene's ambient
is generated at most once per output directory. If the API is unavailable,
the chapter is produced without ambient (logged as warning, not error).

### 5-second cross-fade at scene boundaries

Scene transitions use a 5-second overlap where the outgoing ambient fades
out and the incoming ambient fades in. This is long enough for the listener
to register the environment change without feeling abrupt. Implemented
via ffmpeg `acrossfade` filter.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `ambient_prompt` and `ambient_volume` to `Scene` |
| `src/parsers/ai_section_parser.py` | Extend scene prompt to request `ambient_prompt` and `ambient_volume` |
| `src/tts/ambient_generator.py` | **New module** — generate and cache ambient audio per scene |
| `src/tts/tts_orchestrator.py` | Mix ambient per scene with cross-fade at boundaries |

---

## Open questions

1. Should the 60-second duration be configurable or is it always
   sufficient for looping?
2. Do we need a `--no-ambient` CLI flag to skip ambient generation
   entirely (e.g., for faster iteration during development)?
