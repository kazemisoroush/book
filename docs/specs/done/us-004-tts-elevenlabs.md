# US-004: TTS with ElevenLabs

## Goal

Full end-to-end TTS pipeline using ElevenLabs. The pipeline runs: download → AI parse → save Book JSON → assign voices → synthesise Chapter 1 → output a single `chapter_01.mp3`.

Depends on: US-003 (Character Enrichment) — voice assignment uses `sex` and `age` from the character registry to match ElevenLabs voices to characters.

## Acceptance Criteria

1. `ElevenLabsProvider.synthesize()` uses the v2 SDK (`client.text_to_speech.convert`), not the deprecated v1 `client.generate()`.
2. Voice assignment: each character is assigned a distinct ElevenLabs voice. The narrator gets a voice first. Remaining characters are matched by `sex` and `age` fields.
3. Assignment is deterministic (no random) given the same registry and voice list.
4. NARRATION and DIALOGUE beats are synthesised. ILLUSTRATION, COPYRIGHT, and OTHER beats are skipped.
5. Per-beat MP3s are stitched into `output/chapter_01.mp3` using ffmpeg.
6. Book struct is saved to `output/book.json` as a byproduct of the pipeline run.
7. `audiobook <url> --tts` runs the full pipeline and prints the output path.
8. `audiobook <url> --tts` without `ELEVENLABS_API_KEY` set exits non-zero with a clear error.
9. All existing tests pass. `ruff` and `mypy` clean.

## Out of Scope

- Chapters beyond Chapter 1
- Retry / rate-limit handling
- Caching previously synthesised beats
- LocalTTSProvider voice assignment
- Voice cloning or custom voice upload
