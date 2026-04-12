# US-025 — Fish Audio TTS Provider

## Goal

Implement `TTSProvider` for Fish Audio API as an alternative speech synthesis backend. Fish Audio offers voice cloning, emotion/style control, and competitive pricing compared to ElevenLabs, enabling users to choose their preferred TTS provider for speech synthesis.

---

## Problem

The project currently has only one TTS provider (ElevenLabs). Users cannot:

1. **Choose a different provider** based on cost, quality, or language support preferences
2. **Test alternative voices** without switching entire infrastructure
3. **Gracefully fall back** when ElevenLabs has API issues or rate limits

Fish Audio provides a similar feature set (text-to-speech with emotion/style control) and can serve as a drop-in alternative to ElevenLabs for speech synthesis.

---

## Concept

Implement `FishAudioTTSProvider` following the existing `TTSProvider` interface:

```python
class FishAudioTTSProvider(TTSProvider):
    """Fish Audio implementation of TTSProvider."""

    def __init__(self, api_key: str, base_url: str = "https://api.fish.audio/v1"):
        """Initialize Fish Audio provider.

        Args:
            api_key: Fish Audio API key (from FISH_AUDIO_API_KEY env var)
            base_url: Fish Audio API base URL (default production endpoint)
        """

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesize via Fish Audio API."""

    def get_available_voices(self) -> dict[str, str]:
        """Fetch available voices from Fish Audio."""
```

**API mapping**:
- `text` → Fish Audio `text` parameter
- `voice_id` → Fish Audio `reference_id` (voice model ID)
- `emotion` → mapped to Fish Audio `emotion` parameter (when supported)
- `voice_speed` → Fish Audio `speed` parameter (0.5-2.0 range)
- `previous_text`, `next_text`, `voice_stability`, `voice_style`, `previous_request_ids` → **not supported**, logged as debug and ignored

**Unsupported features**:
Fish Audio does not support prosody context (`previous_text`/`next_text`) or request ID continuity (`previous_request_ids`). When these parameters are provided, log at debug level and proceed without them. This ensures the provider works in the pipeline without errors, but certain advanced TTS features will be gracefully disabled.

**Authentication**:
Uses `Authorization: Bearer {api_key}` header. API key sourced from `FISH_AUDIO_API_KEY` environment variable.

---

## Acceptance criteria

1. New `src/tts/fish_audio_tts_provider.py` module contains `FishAudioTTSProvider` class

2. `FishAudioTTSProvider` implements `TTSProvider` interface:
   - `synthesize()` method accepts all parameters from the interface signature
   - Returns `Optional[str]` (request ID if available, `None` if not supported by Fish Audio)
   - Writes audio to `output_path` as MP3
   - Raises no exceptions on unsupported parameters (logs at debug level instead)

3. `synthesize()` calls Fish Audio TTS API endpoint (`POST /v1/tts`):
   - Request body: `{"text": text, "reference_id": voice_id, "speed": voice_speed, ...}`
   - Response: audio bytes (MP3 format)
   - Writes response body to `output_path`

4. `get_available_voices()` calls Fish Audio voices listing endpoint (`GET /v1/voices`):
   - Returns `dict[str, str]` mapping voice names to voice IDs
   - Caches result in memory for the lifetime of the provider instance (avoid redundant API calls)

5. Unsupported parameters are handled gracefully:
   - `previous_text`, `next_text`: log once at debug level per synthesis call, do not pass to API
   - `voice_stability`, `voice_style`: log once at debug level per synthesis call, do not pass to API
   - `previous_request_ids`: log once at debug level per synthesis call, do not pass to API
   - `emotion`: log at debug if not in Fish Audio's supported emotion set (map supported ones, ignore unsupported)

6. API errors return `None` from `synthesize()` and log at warning level (graceful degradation)

7. `FishAudioTTSProvider` constructor validates API key is non-empty (raises `ValueError` if empty)

8. New unit tests cover:
   - Successful synthesis call (mock Fish Audio API response)
   - Voice listing and caching
   - Unsupported parameter handling (no errors raised, debug logs emitted)
   - API failure handling (returns `None`, logs warning)
   - Constructor validation (rejects empty API key)

9. All existing tests continue to pass (no changes to ElevenLabs provider or orchestrator behavior)

---

## Out of scope

- Fallback logic between providers (covered by US-026 `FallbackTTSProvider`)
- Workflow wiring or provider selection logic (covered by TD-019)
- Config changes (`config.py` API key fields) — deferred to TD-019
- Voice cloning or custom voice creation via Fish Audio API (future enhancement)
- Non-English language support (Fish Audio supports it, but no specific testing or validation in this spec)
- Voice design integration (voice design remains ElevenLabs-specific for now)

---

## Key design decisions

### Why ignore unsupported parameters instead of raising errors?

The `TTSProvider` interface defines a comprehensive parameter set that reflects ElevenLabs' capabilities (prosody context, voice modifiers, request ID continuity). Not all providers support all features. Raising errors would break the pipeline; ignoring them allows the provider to participate with reduced fidelity.

Callers (like `AudioOrchestrator`) don't know which provider is in use. They pass all available context and let the provider decide what to use. Logging at debug level provides visibility without noise in production logs.

### Why cache voices in memory instead of on disk?

Voice lists are small (kilobytes) and change infrequently. An in-memory cache scoped to the provider instance lifetime (one workflow run) is sufficient. Unlike audio files (megabytes), voice metadata doesn't warrant disk persistence.

### Why no prosody context support?

Fish Audio's API does not support `previous_text`/`next_text` parameters as of this spec's writing. Adding client-side prosody simulation (e.g., prepending previous text in the same request) would:
- Violate API usage terms (synthesizing text not intended for the segment)
- Produce incorrect audio (previous segment's text would be audible)
- Require complex trimming logic

It's better to gracefully degrade: TTS works, but lacks prosody continuity. This is an acceptable trade-off for users who prioritize Fish Audio's other benefits (cost, voice quality, language support).

### Why return None for request_id instead of a placeholder?

`previous_request_ids` is used for acoustic continuity in ElevenLabs. Returning a fake ID would mislead callers into thinking continuity is supported. `None` clearly signals "this provider doesn't support request ID tracking."

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/fish_audio_tts_provider.py` | **New module** — `FishAudioTTSProvider` class implementing `TTSProvider` |

---

## Relationship to other specs

- **US-024 (Interface Separation)**: Uses `TTSProvider` interface defined/unchanged by US-024
- **US-026 (OpenAI TTS Fallback)**: Fish Audio can serve as primary with OpenAI as fallback
- **TD-019 (Wire New Providers)**: Wiring into workflow and config deferred to TD-019
- **US-004 (TTS with ElevenLabs)**: Fish Audio is an alternative to ElevenLabs, not a replacement

---

## Implementation notes

- Use `requests` library for HTTP calls (already a dependency)
- Follow existing patterns from `ElevenLabsTTSProvider` for error handling and logging
- Type annotations on all public methods
- Structured logging (`structlog.get_logger(__name__)`)
- TDD: write tests first (mock API responses with `responses` library or similar)
- No mocks beyond the HTTP layer (at most 1 mock per test — the API endpoint)
