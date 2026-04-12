# Eval Spec: Local TTS Provider

**Goal**: Add a `LocalTTSProvider` that wraps the `pyttsx3` library as an
offline TTS fallback in `src/audio/local_tts_provider.py`.

## Acceptance criteria

1. `LocalTTSProvider` is a concrete subclass of `TTSProvider` (from
   `src.audio.tts_provider`).
2. `LocalTTSProvider.__init__(self, rate: int = 150)` stores the speech rate.
3. `synthesize()` writes a zero-byte file to `output_path` and returns `None`
   (stub — real pyttsx3 integration is out of scope).
4. `get_available_voices()` returns `{"default": "local-default"}`.
5. File is named `local_tts_provider.py` (follows the `{vendor}_{capability}_provider.py` convention).
6. Class is named `LocalTTSProvider` (follows the `{Vendor}{Capability}Provider` convention).
7. Test file is named `local_tts_provider_test.py`.

## Files expected to change

- `src/audio/local_tts_provider.py` — new module
- `src/audio/local_tts_provider_test.py` — new test file

## Out of scope

- Actual pyttsx3 integration (synthesize is a stub)
- Voice selection or emotion handling
- No CLI integration
