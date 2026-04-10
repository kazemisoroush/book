# US-027 — Stable Audio Provider (SFX + Ambient)

## Goal

Implement `SoundEffectProvider` and `AmbientProvider` for Stability AI's Stable Audio API, enabling users to generate cinematic sound effects and ambient audio without relying on ElevenLabs. Stable Audio specializes in text-to-audio generation with fine-grained duration control, making it ideal for environmental soundscapes and discrete effects.

---

## Problem

The project currently uses ElevenLabs Sound Effects API for both SFX and ambient audio. This creates:

1. **Single provider dependency** — no alternative if ElevenLabs API is unavailable or cost-prohibitive
2. **No provider comparison** — cannot A/B test different audio generation approaches
3. **Limited specialization** — ElevenLabs is optimized for speech; Stable Audio is purpose-built for environmental sounds

Stable Audio offers competitive quality for non-speech audio generation and serves as a viable alternative or complement to ElevenLabs.

---

## Concept

Two provider implementations sharing a common Stable Audio client:

### 1. StableAudioSoundEffectProvider

```python
class StableAudioSoundEffectProvider(SoundEffectProvider):
    """Stable Audio implementation of SoundEffectProvider."""

    def __init__(self, api_key: str, cache_dir: Path):
        """Initialize Stable Audio SFX provider.

        Args:
            api_key: Stability AI API key (from STABILITY_API_KEY env var)
            cache_dir: Directory for caching generated effects
        """

    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate sound effect via Stable Audio API."""
```

### 2. StableAudioAmbientProvider

```python
class StableAudioAmbientProvider(AmbientProvider):
    """Stable Audio implementation of AmbientProvider."""

    def __init__(self, api_key: str, cache_dir: Path):
        """Initialize Stable Audio ambient provider.

        Args:
            api_key: Stability AI API key (from STABILITY_API_KEY env var)
            cache_dir: Directory for caching generated ambient tracks
        """

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate ambient audio via Stable Audio API."""
```

**API endpoint**: Both use `POST /v2beta/stable-audio/generate/audio` (Stable Audio v2 API)

**Request format**:
```json
{
  "prompt": "{description or prompt}",
  "duration": {duration_seconds},
  "output_format": "mp3"
}
```

**Caching strategy**:
- **SFX**: cache by `SHA256(description)` → `{cache_dir}/{hash}.mp3`
- **Ambient**: cache by `SHA256(prompt)` → `{cache_dir}/{hash}.mp3`

Both follow the ElevenLabs caching pattern for consistency.

**Error handling**:
- API failures return `None` and log at warning level (graceful degradation)
- Invalid responses (non-200, empty body) return `None`
- Network timeouts return `None` after logging

---

## Acceptance criteria

1. New `src/tts/stable_audio_sound_effect_provider.py` module contains `StableAudioSoundEffectProvider` class

2. `StableAudioSoundEffectProvider` implements `SoundEffectProvider` interface:
   - `generate()` calls Stable Audio API with `prompt=description` and `duration=duration_seconds`
   - Checks cache before API call (by description hash)
   - Writes response audio to `output_path` as MP3
   - Returns `output_path` on success, `None` on failure
   - Caches successful results in `{cache_dir}/{sha256(description)}.mp3`

3. New `src/tts/stable_audio_ambient_provider.py` module contains `StableAudioAmbientProvider` class

4. `StableAudioAmbientProvider` implements `AmbientProvider` interface:
   - `generate()` calls Stable Audio API with `prompt=prompt` and `duration=duration_seconds`
   - Checks cache before API call (by prompt hash)
   - Writes response audio to `output_path` as MP3
   - Returns `output_path` on success, `None` on failure
   - Caches successful results in `{cache_dir}/{sha256(prompt)}.mp3`

5. Both providers use `Authorization: Bearer {api_key}` header for authentication

6. Both providers validate API key is non-empty in constructor (raises `ValueError` if empty)

7. Cache directory is created if it doesn't exist (uses `mkdir(parents=True, exist_ok=True)`)

8. API failures are logged at warning level with structured fields:
   - `"stable_audio_sfx_failed"` or `"stable_audio_ambient_failed"`
   - `description`/`prompt`, `duration_seconds`, `error`, `status_code` (if available)

9. Cache hits are logged at debug level:
   - `"stable_audio_sfx_cache_hit"` or `"stable_audio_ambient_cache_hit"`
   - `description`/`prompt`, `cache_path`

10. New unit tests cover:
    - Successful SFX generation (mock Stable Audio API response)
    - Successful ambient generation (mock Stable Audio API response)
    - Cache hit (file exists, no API call)
    - Cache miss (file doesn't exist, API called)
    - API failure handling (returns `None`, logs warning)
    - Constructor validation (rejects empty API key)
    - Cache directory creation

11. All existing tests continue to pass

---

## Out of scope

- Stable Audio Open model support (only hosted API covered)
- Audio format conversion (assume Stable Audio returns MP3 directly)
- Prompt optimization or enhancement (users provide prompts as-is)
- Automatic provider selection based on quality/cost (covered by TD-018)
- Music generation via Stable Audio (future enhancement — Stable Audio supports it, but not in this spec)
- Feature flag auto-adjustment when using Stable Audio (covered by TD-018)

---

## Key design decisions

### Why separate classes instead of one StableAudioProvider?

Even though both SFX and ambient use the same underlying API, they serve different roles in the pipeline:
- **SFX**: triggered by narrative events, cached by description, short duration (2s)
- **Ambient**: triggered by scene changes, cached by scene, longer duration (30-60s)

Separate classes allow different caching strategies (by scene ID vs. by hash) and make dependencies explicit. A single class would require conditional logic based on "mode" — less clear.

### Why SHA256 hash for cache keys instead of scene IDs?

Unlike ElevenLabs ambient (which uses scene IDs from the `Scene` object), Stable Audio providers receive plain strings. They don't have access to `Scene` objects or IDs. Hashing ensures:
- Consistent cache keys across runs (same prompt → same file)
- No filename collisions (different prompts → different files)
- No filesystem-unsafe characters (hashes are always safe)

If a future caller wants scene-ID-based caching, they can wrap the provider or pass the scene ID in the prompt.

### Why MP3 output format?

Consistency with ElevenLabs providers and ffmpeg pipeline expectations. The entire codebase works with MP3. Adding WAV or other formats would require conversion steps.

### Why warning level for failures instead of error?

Following the project's established pattern (US-011, US-023): audio generation failures are non-fatal. The audiobook synthesis continues without the missing element. Warnings surface the issue without stopping the pipeline.

### Why not support Stable Audio's prompt weighting or negative prompts?

Simplicity for v1. Advanced features can be added later without breaking the interface. The base `generate()` method takes a single string prompt. Callers can encode weights/negatives in the prompt text if needed.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/stable_audio_sound_effect_provider.py` | **New module** — `StableAudioSoundEffectProvider` class implementing `SoundEffectProvider` |
| `src/tts/stable_audio_ambient_provider.py` | **New module** — `StableAudioAmbientProvider` class implementing `AmbientProvider` |
| `src/config/config.py` | Add `stability_api_key: Optional[str]` field; load from `STABILITY_API_KEY` env var |

---

## Relationship to other specs

- **US-024 (Interface Separation)**: Implements `SoundEffectProvider` and `AmbientProvider` interfaces defined in US-024
- **US-011 (Ambient)**: Stable Audio ambient is an alternative to ElevenLabs ambient
- **US-023 (SFX)**: Stable Audio SFX is an alternative to ElevenLabs SFX
- **TD-018 (Provider Registry)**: Stable Audio providers will be registered and selectable via config
- **US-028 (Suno Music)**: Separate spec for music generation (Stable Audio CAN do music, but Suno is purpose-built for it)

---

## Implementation notes

- Use `requests` library for HTTP calls (already a dependency)
- Follow existing patterns from `ElevenLabsSoundEffectProvider` and `ElevenLabsAmbientProvider` for caching and error handling
- Type annotations on all public methods
- Structured logging (`structlog.get_logger(__name__)`)
- TDD: write tests first (mock Stable Audio API responses with `responses` library or similar)
- No mocks beyond the HTTP layer (at most 1 mock per test — the API endpoint)
- Timeout for API calls: 60 seconds (Stable Audio generation can be slow)
- Response validation: check `Content-Type: audio/mpeg` before writing to file
