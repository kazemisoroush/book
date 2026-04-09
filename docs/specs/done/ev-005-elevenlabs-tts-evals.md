# EV-005 — Granular ElevenLabs TTS Evals

## Goal

Replace expensive end-to-end TTS workflow runs with targeted, granular evals
for each ElevenLabs API integration point. Each eval calls the real ElevenLabs
API with minimal input and checks the output is structurally valid — confirming
the integration works without synthesizing entire chapters.

---

## Problem

Evaluating TTS quality today requires running the full audiobook pipeline:
download → parse → AI read → voice assign → synthesize all segments → assemble.
This is slow (minutes), expensive (hundreds of API calls), and gives no
diagnostic granularity — if something breaks, you don't know which layer failed.

The ElevenLabs integration has 3 distinct API call sites, each with different
failure modes:

1. **`elevenlabs_provider.py`** — `text_to_speech.convert()` for speech synthesis
2. **`voice_designer.py`** — `text_to_voice.create_previews()` + `create()` for voice design
3. **`ambient_generator.py` / `sound_effects_generator.py`** — `text_to_sound_effects.convert()` for audio effects

A single targeted API call to each is far cheaper than a full e2e run, and
pinpoints failures to the exact module.

---

## Concept

### Eval structure

One scorer per API integration point, each calling the real ElevenLabs API
with a single, minimal request:

| Eval | API called | Input | Expected output |
|------|-----------|-------|-----------------|
| `score_tts_synthesis` | `text_to_speech.convert` | 1 short sentence + voice_id | Valid MP3 bytes (> 1 KB) |
| `score_voice_design` | `text_to_voice.create_previews` + `create` | 1 voice description | Valid voice_id string |
| `score_ambient_audio` | `text_to_sound_effects.convert` | 1 ambient prompt | Valid MP3 bytes (> 1 KB) |
| `score_sound_effects` | `text_to_sound_effects.convert` | 1 SFX description | Valid MP3 bytes (> 1 KB) |

### Cost model

Each eval makes 1-2 API calls. Compared to e2e (200+ calls per chapter):
- TTS synthesis: 1 call (~0.01 of a chapter)
- Voice design: 2 calls (preview + create)
- Ambient: 1 call
- Sound effects: 1 call

Total: ~5 API calls per full eval suite run vs. 200+ for a single chapter e2e.

### What we check

These evals are **integration smoke tests**, not quality assessments. They
verify:
1. API credentials work
2. SDK version is compatible
3. Response format matches expectations (MP3 bytes, voice ID string)
4. Error handling works (bad input → graceful failure, not crash)

Audio quality evaluation (does it sound good?) is out of scope — that requires
human ears and is a future spec.

---

## Acceptance criteria

1. **`src/evals/score_tts_synthesis.py`** exists and subclasses `EvalHarness`:
   - `setup()`: no-op (no fixtures needed — uses real API)
   - `score()`: calls `ElevenLabsProvider.synthesize()` with a short test
     sentence and a known voice_id (use "Rachel" or similar default voice)
   - Recall checks:
     - Returns bytes (not None, not empty)
     - Returned bytes are > 1024 (valid audio, not an error page)
     - Returned bytes start with valid MP3/MPEG header
   - Precision checks:
     - Passing an empty string as text returns gracefully (no crash)
   - `cleanup()`: removes any temp files created during scoring

2. **`src/evals/score_voice_design.py`** exists and subclasses `EvalHarness`:
   - `setup()`: no-op
   - `score()`: calls `design_voice()` with a test description
     (e.g., "A warm, gentle female voice in her 30s")
   - Recall checks:
     - Returns a non-empty string (voice_id)
     - Voice_id can be looked up via `client.voices.get()`
   - Precision checks:
     - Passing an empty description doesn't crash
   - `cleanup()`: deletes the test voice from ElevenLabs account via API

3. **`src/evals/score_ambient_audio.py`** exists and subclasses `EvalHarness`:
   - `setup()`: creates a temp output directory
   - `score()`: calls `get_ambient_audio()` with a test Scene
     (e.g., ambient_prompt="quiet library with occasional page turns")
   - Recall checks:
     - Returns a Path (not None)
     - File exists on disk
     - File size > 1024 bytes
   - Precision checks:
     - Scene with `ambient_prompt=None` returns None (no API call)
   - `cleanup()`: removes temp output directory

4. **`src/evals/score_sound_effects.py`** exists and subclasses `EvalHarness`:
   - `setup()`: creates a temp output directory
   - `score()`: calls `get_sound_effect()` with a test description
     (e.g., "firm knock on wooden door")
   - Recall checks:
     - Returns a Path (not None)
     - File exists on disk
     - File size > 1024 bytes
     - Second call with same description returns cached file (no new API call)
   - Precision checks:
     - Passing `client=None` returns None (no crash)
   - `cleanup()`: removes temp output directory

5. All scorers use `EvalHarness` base class and follow the existing pattern
   (see `src/evals/score_ai_read.py` for reference).

6. All scorers require `ELEVEN_API_KEY` environment variable. If missing,
   `setup()` prints an error and exits cleanly (not a test failure — a
   configuration issue).

7. Each scorer is runnable standalone:
   ```bash
   python -m src.evals.score_tts_synthesis score
   python -m src.evals.score_voice_design score
   python -m src.evals.score_ambient_audio score
   python -m src.evals.score_sound_effects score
   ```

8. A convenience runner `src/evals/run_tts_evals.py` runs all 4 scorers in
   sequence and reports a combined pass/fail.

9. All existing tests continue to pass (`make test`, `make lint`).

---

## Out of scope

- Audio quality evaluation (does it sound good?) — requires human ears
- Latency benchmarking (how fast is the API?) — future spec
- Cost tracking (how much does each call cost?) — future spec
- Load testing (can we make 100 concurrent calls?) — future spec
- Voice comparison (does voice A sound like voice B?) — future spec
- Testing with different ElevenLabs models (v2 vs v3) — future spec
- Mocking the ElevenLabs API — these are real integration evals

---

## Key design decisions

### Real API calls, not mocks

The unit tests in `*_test.py` already mock the ElevenLabs client extensively.
These evals exist precisely to verify the real API integration works. They
must call the real API.

### Minimal input per eval

Each eval uses the smallest possible input that exercises the API path. One
sentence for TTS, one description for voice design, one prompt for ambient/SFX.
This keeps cost low while still verifying the integration.

### Cleanup deletes created resources

Voice design creates permanent voices in the ElevenLabs account. The cleanup
step must delete them to avoid polluting the account. Ambient and SFX audio
files are local and just need temp directory cleanup.

### 100% threshold (not 80%)

Unlike AI evals (which tolerate non-determinism), these are integration smoke
tests. The API either works or it doesn't — there's no "80% working."
Threshold is 100% for all checks.

---

## Files changed (expected)

| File | Change |
|------|--------|
| `src/evals/score_tts_synthesis.py` | **New** — TTS synthesis eval |
| `src/evals/score_voice_design.py` | **New** — Voice design eval |
| `src/evals/score_ambient_audio.py` | **New** — Ambient audio eval |
| `src/evals/score_sound_effects.py` | **New** — Sound effects eval |
| `src/evals/run_tts_evals.py` | **New** — Combined runner |

---

## Relationship to other specs

- **EV-001 (Eval Framework)**: These evals subclass `EvalHarness` from that refactor
- **EV-002 (Eval Agent)**: The Eval Agent could write these, but the spec is detailed enough for the Coder Agent
- **US-023 (Cinematic SFX)**: Tests the sound_effects_generator integration
- **US-011 (Ambient Sound)**: Tests the ambient_generator integration
- **US-014 (Character Voice Design)**: Tests the voice_designer integration
- **TD-011 (Reuse Designed Voices)**: Voice design eval should be updated when TD-011 ships

---

## Implementation notes

- Use `os.environ.get("ELEVEN_API_KEY")` — do not import from config layer (evals should be self-contained)
- The ElevenLabs Python SDK is `elevenlabs` (already in dependencies)
- For TTS synthesis, use a well-known voice ID (e.g., "Rachel" — look up via `client.voices.get_all()` and pick the first)
- For voice design cleanup, use `client.voices.delete(voice_id)`
- Keep the test sentence short to minimize credit usage: "The quick brown fox jumped over the lazy dog."
- Ambient and SFX generators already handle `client=None` gracefully — use this for precision checks
