# US-028 — Suno AI Music Provider

## Goal

Implement `MusicProvider` for Suno AI's music generation API, enabling background music generation from mood/style prompts. Suno specializes in full-length, high-quality music generation with genre/mood control, making it ideal for chapter-level background music that elevates the audiobook's emotional impact.

---

## Problem

US-012 (Background Music) defines music generation using ElevenLabs Music API. However:

1. **ElevenLabs Music API is not yet implemented** in the project — US-012 is still in backlog
2. **Suno is purpose-built for music** — ElevenLabs is a TTS company; Suno is a music generation company
3. **No music provider interface exists** — US-024 defines it, but no concrete implementations exist yet

Suno offers superior music quality, longer generation lengths (up to 4 minutes per track), and fine-grained genre/mood control, making it the better choice for audiobook background music.

---

## Concept

Implement `MusicProvider` for Suno AI:

```python
class SunoMusicProvider(MusicProvider):
    """Suno AI implementation of MusicProvider."""

    def __init__(self, api_key: str, cache_dir: Path):
        """Initialize Suno music provider.

        Args:
            api_key: Suno AI API key (from SUNO_API_KEY env var)
            cache_dir: Directory for caching generated music tracks
        """

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate music via Suno AI API."""
```

**API flow** (Suno uses async generation):
1. Submit generation request: `POST /api/generate` with `{"prompt": prompt, "duration": duration_seconds}`
2. Receive task ID: `{"id": "task_123"}`
3. Poll status: `GET /api/task/{task_id}` until `status == "complete"`
4. Download audio: `GET /api/download/{task_id}` → MP3 bytes
5. Write to `output_path`

**Caching strategy**:
Cache by `SHA256(prompt)` → `{cache_dir}/{hash}.mp3`

Unlike ElevenLabs (where same prompt → same audio), Suno is non-deterministic (same prompt → different audio each time). However, caching still makes sense:
- **Within a run**: same mood/prompt used multiple times → reuse first result
- **Across runs**: same book re-synthesized → reuse previous music (consistency)

If users want fresh music, they delete the cache directory.

**Polling configuration**:
- Max wait time: 120 seconds (Suno generation is slow)
- Poll interval: 5 seconds
- If timeout, return `None` and log warning

---

## Acceptance criteria

1. New `src/tts/suno_music_provider.py` module contains `SunoMusicProvider` class

2. `SunoMusicProvider` implements `MusicProvider` interface:
   - `generate()` checks cache first (by prompt hash)
   - If cache miss, calls Suno API to generate music
   - Polls task status until complete or timeout
   - Downloads audio and writes to `output_path` as MP3
   - Caches result in `{cache_dir}/{sha256(prompt)}.mp3`
   - Returns `output_path` on success, `None` on failure/timeout

3. API request format (`POST /api/generate`):
   ```json
   {
     "prompt": "{prompt}",
     "duration": {duration_seconds},
     "model": "chirp-v3",
     "instrumental": false
   }
   ```
   - `model`: use `"chirp-v3"` (Suno's latest as of spec writing; hardcoded, not configurable)
   - `instrumental`: use `false` (allows vocals if prompt requests them; most audiobook music is instrumental but not enforcing it)

4. Polling logic:
   - Poll `GET /api/task/{task_id}` every 5 seconds
   - Stop when `status == "complete"` or timeout (120s)
   - If `status == "failed"`, return `None` and log error
   - If timeout, return `None` and log warning with task ID

5. Authentication: `Authorization: Bearer {api_key}` header for all requests

6. Constructor validates API key is non-empty (raises `ValueError` if empty)

7. Cache directory is created if it doesn't exist (uses `mkdir(parents=True, exist_ok=True)`)

8. API failures are logged at warning level with structured fields:
   - `"suno_music_generation_failed"` or `"suno_music_timeout"`
   - `prompt`, `duration_seconds`, `task_id`, `error`

9. Cache hits are logged at debug level:
   - `"suno_music_cache_hit"`
   - `prompt`, `cache_path`

10. Generation success is logged at info level:
    - `"suno_music_generated"`
    - `prompt`, `duration_seconds`, `task_id`, `cache_path`

11. New unit tests cover:
    - Successful music generation (mock Suno API responses: submit → poll → download)
    - Cache hit (file exists, no API call)
    - Cache miss (file doesn't exist, API called)
    - Task failure (status="failed")
    - Timeout (status never becomes "complete")
    - API failure handling (returns `None`, logs warning)
    - Constructor validation (rejects empty API key)
    - Cache directory creation

12. All existing tests continue to pass

---

## Out of scope

- Vocal/instrumental control (use `instrumental: false` always; users control via prompt)
- Model selection (hardcode `chirp-v3`; future enhancement if Suno releases new models)
- Prompt optimization or style presets (covered by US-012's mood enum → prompt mapping)
- Music length adjustments (if generated track is shorter/longer than requested, use as-is; ffmpeg looping handles length matching in orchestrator)
- Integration with US-012's `MusicMood` enum (US-012 spec needs updating to support provider abstraction; out of scope for this spec)
- Feature flag auto-adjustment (covered by TD-018)
- Cost tracking or quota management (future enhancement)

---

## Key design decisions

### Why cache non-deterministic generation?

Even though Suno produces different audio each time, caching provides:
- **Consistency within a book** — Chapter 1 "tense" and Chapter 5 "tense" use the same track (coherent experience)
- **Faster re-runs** — iterating on TTS settings doesn't regenerate music
- **Cost savings** — each generation costs credits

Users who want fresh music can clear the cache explicitly.

### Why 120-second timeout instead of waiting indefinitely?

Suno generation typically takes 30-60 seconds. A 120s timeout allows for slow API days without blocking synthesis indefinitely. If timeout occurs, the audiobook continues without music (graceful degradation).

### Why poll every 5 seconds instead of webhooks?

Simplicity. Webhooks require:
- External HTTP endpoint
- Firewall/NAT configuration
- Webhook verification logic

Polling adds ~2-5 seconds latency (negligible for a 60-second generation) and is trivial to implement.

### Why not support custom models or advanced parameters?

Focus on the 80% use case: prompt-to-music with sensible defaults. Advanced users can subclass `SunoMusicProvider` or fork it. Keeping the interface simple reduces testing surface and maintenance burden.

### Why MP3 output format?

Consistency with all other audio providers. The ffmpeg pipeline expects MP3. Suno supports MP3 natively.

### Why not implement ElevenLabsMusicProvider instead?

Suno is the superior product for music generation:
- **Longer tracks** — up to 4 minutes (ElevenLabs Music API maxes at ~30 seconds)
- **Higher quality** — Suno's models are state-of-the-art for music
- **Better genre control** — Suno understands nuanced prompts ("lo-fi jazz with rain sounds")

ElevenLabs Music API can be added later as an alternative (simpler, faster, but lower quality).

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/suno_music_provider.py` | **New module** — `SunoMusicProvider` class implementing `MusicProvider` |
| `src/config/config.py` | Add `suno_api_key: Optional[str]` field; load from `SUNO_API_KEY` env var |

---

## Relationship to other specs

- **US-024 (Interface Separation)**: Implements `MusicProvider` interface defined in US-024
- **US-012 (Background Music)**: This spec provides the music provider needed by US-012; US-012 needs updating to use provider abstraction
- **TD-018 (Provider Registry)**: Suno provider will be registered and selectable via config
- **US-027 (Stable Audio)**: Stable Audio supports music generation too, but Suno is purpose-built for it

---

## Implementation notes

- Use `requests` library for HTTP calls (already a dependency)
- Type annotations on all public methods
- Structured logging (`structlog.get_logger(__name__)`)
- TDD: write tests first (mock Suno API responses: submit/poll/download)
- No mocks beyond the HTTP layer (at most 1 mock per test — the API endpoints)
- Polling: use `time.sleep(5)` between polls (simple; not async — entire TTS pipeline is synchronous)
- Response validation: check `Content-Type: audio/mpeg` before writing to file
- Task ID storage: keep in memory only (no need to persist; if process dies, re-run will skip via cache)
