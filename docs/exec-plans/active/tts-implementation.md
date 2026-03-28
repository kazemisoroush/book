# ExecPlan: TTS Implementation — End-to-End Audio Generation

## Goal

Full TTS pipeline: fix `ElevenLabsProvider` (v1→v2 SDK), add voice assignment
(sex/age-aware using `Character.sex` / `Character.age` from US-001), audio
assembly, workflow integration, and a `--tts` CLI flag.

Output: `output/chapter_01.mp3`
Pipeline: `download → AI parse → save Book JSON → TTS → output/chapter_01.mp3`

**Depends on:** US-004 must be complete — `Character.sex` and `Character.age`
must exist before executing this plan.

## Source

User story: `docs/product-specs/us-005-tts-elevenlabs.md`

---

## Deliverables

### Step 1 — Fix ElevenLabsProvider to use v2 SDK

Replace `client.generate()` with `client.text_to_speech.convert(voice_id=..., text=..., model_id=...)`.
`get_available_voices()` already uses `client.voices.get_all()` — keep it.

**Files changed:** `src/tts/elevenlabs_provider.py`, `src/tts/elevenlabs_provider_test.py` (new)

---

### Step 2 — VoiceAssignment model and assign_voices interface

Add `VoiceAssignment` dataclass (`assignments: dict[str, str]` — character_id → voice_id)
to `src/tts/models.py`. Add abstract `assign_voices(registry: CharacterRegistry) -> VoiceAssignment`
to `TTSProvider`.

**Files changed:** `src/tts/tts_provider.py`, `src/tts/models.py` (new), `src/tts/models_test.py` (new)

---

### Step 3 — Implement ElevenLabsProvider.assign_voices

Fetch available voices, assign narrator first, then match remaining characters
by `Character.sex` and `Character.age`. Deterministic (stable sort, no random).
Raises `RuntimeError` if more characters than available voices.

**Files changed:** `src/tts/elevenlabs_provider.py`

---

### Step 4 — Audio assembly module

`src/tts/audio_assembler.py` — single function `assemble_chapter(segments, output_path, ffmpeg_path)`.
Concatenates per-segment MP3s using ffmpeg concat demuxer. Raises `RuntimeError`
if ffmpeg not found or exits non-zero.

**Files changed:** `src/tts/audio_assembler.py` (new), `src/tts/audio_assembler_test.py` (new)

---

### Step 5 — TTSWorkflow: Chapter 1 synthesis

`TTSWorkflow.run(book, output_dir) -> Path` — assigns voices, iterates Chapter 1
segments, skips ILLUSTRATION/COPYRIGHT/OTHER, calls `synthesize()` per
NARRATION/DIALOGUE segment, assembles to `output_dir/chapter_01.mp3`. Segment
files kept in `output_dir/segments/` as debugging artifacts.

**Files changed:** `src/tts/tts_workflow.py` (new), `src/tts/tts_workflow_test.py` (new)

---

### Step 6 — CLI: --tts flag

Add `--tts` flag to `main.py`. When set: save Book JSON to `output/book.json`,
create `ElevenLabsProvider` from `ELEVENLABS_API_KEY` (abort with clear error
if missing), run `TTSWorkflow`, print output path.

**Files changed:** `src/main.py`, `src/main_test.py` (new or updated)

---

## Acceptance Criteria

1. `synthesize()` calls `client.text_to_speech.convert` — confirmed by mock test.
2. `VoiceAssignment` is a typed dataclass; `assign_voices()` covers every character in the registry.
3. Voice assignment uses `Character.sex` and `Character.age`; deterministic.
4. `assemble_chapter()` uses ffmpeg concat demuxer; raises `RuntimeError` if ffmpeg missing.
5. `TTSWorkflow.run()` synthesises only NARRATION/DIALOGUE segments; skips the rest.
6. `--tts` without `ELEVENLABS_API_KEY` exits non-zero with a clear error.
7. All existing passing tests continue to pass. `ruff` and `mypy` clean.

---

## Out of Scope

- Chapters beyond Chapter 1
- Retry / rate-limit handling
- Caching synthesised segment files
- LocalTTSProvider voice assignment
- Voice cloning or custom voice upload
