# US-026 — OpenAI TTS Fallback Provider

## Goal

Implement `TTSProvider` for OpenAI TTS API as a reliable fallback option. OpenAI TTS has simpler capabilities (no emotion tags, no prosody context) but offers high availability and predictable pricing, making it ideal as a safety net when primary providers (ElevenLabs, Fish Audio) encounter rate limits or outages.

---

## Problem

The project currently has no fallback mechanism when the primary TTS provider fails. This creates single points of failure:

1. **ElevenLabs rate limits** — monthly quota exhaustion stops synthesis mid-book
2. **API outages** — provider downtime blocks all TTS work
3. **Cost optimization** — cannot use a cheaper fallback for low-priority content (e.g., narrator text)

OpenAI TTS offers a stable, widely available alternative with adequate quality for fallback scenarios.

---

## Concept

Two components:

### 1. OpenAITTSProvider

Direct OpenAI TTS API implementation:

```python
class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS implementation of TTSProvider."""

    def __init__(self, api_key: str, model: str = "tts-1"):
        """Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key (from OPENAI_API_KEY env var)
            model: TTS model ID ("tts-1" or "tts-1-hd")
        """

    def synthesize(...) -> Optional[str]:
        """Synthesize via OpenAI TTS API."""

    def get_available_voices(self) -> dict[str, str]:
        """Return OpenAI's 6 built-in voices."""
```

**API mapping**:
- `text` → OpenAI `input` parameter
- `voice_id` → OpenAI `voice` parameter (one of: alloy, echo, fable, onyx, nova, shimmer)
- `voice_speed` → OpenAI `speed` parameter (0.25–4.0 range, clamp to valid range)
- `emotion`, `previous_text`, `next_text`, `voice_stability`, `voice_style`, `previous_request_ids` → **not supported**, ignored

**Voice mapping**:
OpenAI provides 6 fixed voices. `get_available_voices()` returns a hardcoded dict:
```python
{
    "alloy": "alloy",
    "echo": "echo",
    "fable": "fable",
    "onyx": "onyx",
    "nova": "nova",
    "shimmer": "shimmer",
}
```

If a `voice_id` not in this set is passed to `synthesize()`, default to `"alloy"` and log a warning.

### 2. FallbackTTSProvider

Wrapper that tries a primary provider first, then a fallback:

```python
class FallbackTTSProvider(TTSProvider):
    """TTSProvider wrapper that falls back to a secondary provider on failure."""

    def __init__(
        self,
        primary: TTSProvider,
        fallback: TTSProvider,
        fallback_on: type[Exception] | tuple[type[Exception], ...] = Exception,
    ):
        """Initialize fallback wrapper.

        Args:
            primary: The primary TTS provider to try first.
            fallback: The fallback provider to use if primary fails.
            fallback_on: Exception type(s) that trigger fallback (default: all).
        """

    def synthesize(...) -> Optional[str]:
        """Try primary; on failure, try fallback."""

    def get_available_voices(self) -> dict[str, str]:
        """Return primary's voices (fallback's voices not exposed)."""
```

**Fallback logic**:
1. Call `primary.synthesize(...)` with all parameters
2. If successful (returns without exception), return the result
3. If raises exception in `fallback_on` tuple, log warning and call `fallback.synthesize(...)`
4. If fallback also fails, re-raise the fallback's exception

**Usage example**:
```python
primary = ElevenLabsProvider(api_key=...)
fallback = OpenAITTSProvider(api_key=...)
provider = FallbackTTSProvider(primary, fallback)
```

---

## Acceptance criteria

1. New `src/tts/openai_tts_provider.py` module contains `OpenAITTSProvider` class

2. `OpenAITTSProvider` implements `TTSProvider` interface:
   - `synthesize()` calls OpenAI TTS API (`POST /v1/audio/speech`)
   - Request body: `{"model": model, "voice": voice_id, "input": text, "speed": voice_speed}`
   - Writes audio response to `output_path` as MP3
   - Returns `None` (OpenAI does not provide request IDs)

3. `OpenAITTSProvider.synthesize()` parameter handling:
   - `voice_speed`: clamp to OpenAI's valid range (0.25–4.0); if `None`, omit from request (use API default 1.0)
   - `voice_id`: if not in OpenAI's 6 voices, default to `"alloy"` and log warning
   - Unsupported parameters (`emotion`, `previous_text`, `next_text`, `voice_stability`, `voice_style`, `previous_request_ids`): ignore silently (no logs — expected behavior for fallback)

4. `OpenAITTSProvider.get_available_voices()` returns hardcoded dict of 6 voices (no API call)

5. `OpenAITTSProvider` constructor validates API key is non-empty (raises `ValueError` if empty)

6. New `src/tts/fallback_tts_provider.py` module contains `FallbackTTSProvider` class

7. `FallbackTTSProvider` implements `TTSProvider` interface:
   - `synthesize()` tries primary first, falls back on exception
   - Logs primary failure at warning level: `"tts_primary_failed, falling_back_to_secondary"`
   - Logs fallback success at info level: `"tts_fallback_succeeded"`
   - Re-raises fallback's exception if both fail
   - `get_available_voices()` delegates to primary only (fallback voices not exposed)

8. `FallbackTTSProvider.synthesize()` passes all parameters to both providers (no filtering)

9. New unit tests cover:
   - `OpenAITTSProvider` successful synthesis (mock OpenAI API)
   - Voice clamping (invalid voice → `"alloy"`)
   - Speed clamping (out-of-range speed → clamped to 0.25–4.0)
   - API failure handling
   - `FallbackTTSProvider` fallback success (primary raises, fallback succeeds)
   - `FallbackTTSProvider` fallback failure (both raise → re-raises fallback's exception)
   - `FallbackTTSProvider` primary success (fallback never called)

10. All existing tests continue to pass

---

## Out of scope

- Automatic voice mapping between providers (e.g., mapping ElevenLabs voices to OpenAI voices) — user must handle voice selection
- Selective fallback by content type (e.g., narrator only) — future enhancement
- Workflow wiring or provider selection logic (covered by TD-019)
- Config changes (`config.py` API key fields) — deferred to TD-019
- Caching OpenAI voices (hardcoded dict needs no cache)
- Fallback for `get_available_voices()` (if primary's voice listing fails, raise; don't fallback)

---

## Key design decisions

### Why OpenAI TTS instead of another provider?

OpenAI TTS is:
- **Highly available** — same infrastructure as ChatGPT
- **Predictable pricing** — $15/million characters, no monthly quotas
- **Simple API** — fewer moving parts = fewer failure modes
- **Adequate quality** — not as expressive as ElevenLabs, but acceptable for fallback

These qualities make it ideal as a safety net.

### Why return hardcoded voices instead of calling the API?

OpenAI TTS has exactly 6 voices, unchanging since launch. Hardcoding them avoids an unnecessary API call and startup dependency. If OpenAI adds voices in the future, we update the hardcoded dict in a maintenance PR.

### Why FallbackTTSProvider as a wrapper instead of built-in logic?

Separation of concerns: `OpenAITTSProvider` is a pure OpenAI client; `FallbackTTSProvider` is a composition pattern. This allows:
- Using OpenAI as primary (not just fallback)
- Composing any two providers (ElevenLabs → OpenAI, Fish Audio → OpenAI, etc.)
- Testing each independently

### Why re-raise fallback's exception instead of returning None?

If both providers fail, the user needs to know. Returning `None` would silently skip the segment. Re-raising ensures the error surfaces clearly in logs and can be caught by higher-level retry logic.

### Why pass all parameters to fallback?

Even though OpenAI ignores most parameters, the wrapper should be provider-agnostic. If we later use a different fallback provider that DOES support prosody context, it should receive those parameters without wrapper changes.

### Why not expose fallback's voices in get_available_voices()?

Voice assignment happens once at the start of synthesis. The primary provider's voices are used for character→voice mapping. If synthesis falls back mid-book, the same voice IDs are passed to the fallback provider. The fallback must handle voice ID mismatches gracefully (defaulting to a sensible voice).

Exposing fallback voices in `get_available_voices()` would confuse voice assignment — it would see voices from both providers mixed together.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/openai_tts_provider.py` | **New module** — `OpenAITTSProvider` class implementing `TTSProvider` |
| `src/tts/fallback_tts_provider.py` | **New module** — `FallbackTTSProvider` wrapper class |

---

## Relationship to other specs

- **US-024 (Interface Separation)**: Uses `TTSProvider` interface
- **US-025 (Fish Audio)**: Fish Audio can be primary with OpenAI as fallback
- **TD-019 (Wire New Providers)**: Wiring into workflow and config deferred to TD-019
- **US-004 (TTS with ElevenLabs)**: OpenAI is an alternative/fallback to ElevenLabs, not a replacement

---

## Implementation notes

- Use `openai` Python SDK (add as dependency: `openai>=1.0.0`)
- Follow existing patterns from `ElevenLabsTTSProvider` for error handling and logging
- Type annotations on all public methods
- Structured logging (`structlog.get_logger(__name__)`)
- TDD: write tests first (mock OpenAI SDK responses)
- No mocks beyond the OpenAI SDK client (at most 1 mock per test)
- Voice clamping logic: use a set for O(1) lookup, default to `"alloy"` on mismatch
- Speed clamping: `max(0.25, min(4.0, speed))` if provided, else omit from request
