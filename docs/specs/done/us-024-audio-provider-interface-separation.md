# US-024 — Audio Provider Interface Separation

## Goal

Separate the four distinct audio generation concerns (speech, sound effects, ambient audio, music) into independent provider interfaces so each can use a different backend. This enables mixing providers — e.g., Fish Audio for speech, Stable Audio for ambient and SFX, Suno for music — without coupling their implementations.

---

## Problem

The current codebase has one abstract interface (`TTSProvider`) covering only speech synthesis. Sound effects, ambient audio, and music generation are handled by standalone functions (`get_sound_effect()`, `get_ambient_audio()`) that directly call the ElevenLabs API. This tight coupling prevents:

1. **Swapping providers per concern** — cannot use Stable Audio for ambient while keeping ElevenLabs for speech
2. **Testing without API calls** — no interface to mock, so tests must call the real ElevenLabs SDK or skip coverage
3. **Provider fallback logic** — cannot gracefully switch to OpenAI TTS when ElevenLabs is unavailable

Each audio generation concern needs its own abstract interface, allowing concrete implementations to be swapped independently.

---

## Concept

Introduce three new provider ABCs alongside the existing `TTSProvider`:

```python
class TTSProvider(ABC):
    """Speech synthesis: text → voice audio."""
    @abstractmethod
    def synthesize(...) -> Optional[str]: ...
    @abstractmethod
    def get_available_voices() -> dict[str, str]: ...

class SoundEffectProvider(ABC):
    """Discrete event sounds: description → SFX audio."""
    @abstractmethod
    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]: ...

class AmbientProvider(ABC):
    """Environmental background audio: prompt → loopable ambient."""
    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]: ...

class MusicProvider(ABC):
    """Background music: mood/prompt → music track."""
    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]: ...
```

Each interface returns `Optional[Path]` — `None` indicates graceful failure (logged, not raised).

**Caching**: Each provider implementation is responsible for its own caching strategy. The interface does not mandate caching, but ElevenLabs implementations will continue to cache by hash/key to avoid redundant API calls.

**Module structure**:
- New: `src/tts/sound_effect_provider.py` — `SoundEffectProvider` ABC
- New: `src/tts/ambient_provider.py` — `AmbientProvider` ABC
- New: `src/tts/music_provider.py` — `MusicProvider` ABC
- Modified: `src/tts/sound_effects_generator.py` → `src/tts/elevenlabs_sound_effect_provider.py` (concrete impl)
- Modified: Extract ElevenLabs ambient generation logic from inline usage → `src/tts/elevenlabs_ambient_provider.py`
- Future: `src/tts/elevenlabs_music_provider.py` (per US-012)

---

## Acceptance criteria

1. `src/tts/sound_effect_provider.py` contains `SoundEffectProvider` ABC with signature:
   ```python
   @abstractmethod
   def generate(
       self,
       description: str,
       output_path: Path,
       duration_seconds: float = 2.0,
   ) -> Optional[Path]:
       """Generate a sound effect from description.

       Returns:
           Path to generated audio file, or None on failure.
       """
   ```

2. `src/tts/ambient_provider.py` contains `AmbientProvider` ABC with signature:
   ```python
   @abstractmethod
   def generate(
       self,
       prompt: str,
       output_path: Path,
       duration_seconds: float = 60.0,
   ) -> Optional[Path]:
       """Generate ambient audio from natural-language prompt.

       Returns:
           Path to generated audio file, or None on failure.
       """
   ```

3. `src/tts/music_provider.py` contains `MusicProvider` ABC with signature:
   ```python
   @abstractmethod
   def generate(
       self,
       prompt: str,
       output_path: Path,
       duration_seconds: float = 60.0,
   ) -> Optional[Path]:
       """Generate music from mood/style prompt.

       Returns:
           Path to generated audio file, or None on failure.
       """
   ```

4. New `src/tts/elevenlabs_sound_effect_provider.py`:
   - Contains `ElevenLabsSoundEffectProvider` class implementing `SoundEffectProvider`
   - Constructor accepts `client: ElevenLabs` and `cache_dir: Path`
   - `generate()` method wraps the current `get_sound_effect()` logic (API call + caching by description hash)
   - Cache key remains `SHA256(description)` → `{cache_dir}/{hash}.mp3`
   - Returns `None` on API failure (logged as warning, not error)
   - **`src/tts/sound_effects_generator.py` remains unchanged** as a convenience function wrapper (calls the provider internally)

5. New `src/tts/elevenlabs_ambient_provider.py`:
   - Contains `ElevenLabsAmbientProvider` class implementing `AmbientProvider`
   - Constructor accepts `client: ElevenLabs` and `cache_dir: Path`
   - `generate()` wraps current `get_ambient_audio()` logic (calls ElevenLabs Sound Effects API with ambient prompts)
   - Cache key: scene ID (from function signature) → `{cache_dir}/{scene_id}.mp3`
   - Returns `None` on API failure
   - **`src/tts/ambient_generator.py` remains unchanged** as a convenience function wrapper (calls the provider internally)

6. `src/tts/tts_orchestrator.py` is updated:
   - Constructor accepts optional `sound_effect_provider: Optional[SoundEffectProvider] = None` and `ambient_provider: Optional[AmbientProvider] = None`
   - Removes direct imports of `get_sound_effect()` and `get_ambient_audio()` functions
   - Uses `sound_effect_provider.generate()` when inserting SFX into silence gaps
   - Uses `ambient_provider.generate()` when mixing ambient audio
   - Graceful skip when provider is `None` (same as current behavior when client is `None`)

7. All existing tests continue to pass

8. New unit tests cover:
   - Each ABC can be subclassed and instantiated
   - `ElevenLabsSoundEffectProvider` implements the interface correctly
   - `ElevenLabsAmbientProvider` implements the interface correctly
   - Caching behavior for both providers (cache hit, cache miss, API failure)
   - `TTSOrchestrator` skips SFX/ambient gracefully when provider is `None`

---

## Out of scope

- Concrete implementations for Stable Audio, OpenAI, Suno, Fish Audio (covered by US-025 through US-028)
- Provider registry/factory pattern (covered by TD-018)
- Configuration for selecting providers (covered by TD-018)
- Voice design provider interface (voice design is part of voice assignment, not audio generation)
- Removing convenience functions `get_sound_effect()` and `get_ambient_audio()` (kept for backward compatibility; internally delegate to providers)
- Automatic feature flag gating based on provider capabilities (covered by TD-018)

---

## Key design decisions

### Why separate interfaces instead of one unified AudioProvider?

Each audio generation task has different input/output contracts:
- **Speech**: text + voice_id + emotion context → audio + request_id
- **SFX**: description + duration → audio
- **Ambient**: prompt + duration → loopable audio
- **Music**: mood/prompt + duration → music track

Merging them into one interface would require optional parameters and type unions, obscuring the actual capabilities. Separate interfaces make dependencies explicit and enable targeted mocking.

### Why Optional[Path] return instead of raising exceptions?

The project's established pattern (from US-011, US-023) is graceful degradation: if an audio generation API fails, the audiobook synthesis continues without that element. Returning `None` keeps this pattern consistent across all providers.

### Why move caching into the provider implementation?

Different providers may have different caching strategies:
- ElevenLabs: cache by hash (same input → same audio)
- Suno: cache by request ID (non-deterministic generation)
- Stable Audio: cache by hash + model version

Making caching an implementation detail allows each provider to choose the right strategy.

### Why keep TTSProvider unchanged?

`TTSProvider` already has a well-defined interface with extensive usage across the codebase. Changing it would ripple through 10+ files. The new providers are additive, not modifications.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/sound_effect_provider.py` | **New module** — `SoundEffectProvider` ABC |
| `src/tts/ambient_provider.py` | **New module** — `AmbientProvider` ABC |
| `src/tts/music_provider.py` | **New module** — `MusicProvider` ABC |
| `src/tts/elevenlabs_sound_effect_provider.py` | **New module** — provider implementation wrapping SFX logic |
| `src/tts/elevenlabs_ambient_provider.py` | **New module** — provider implementation wrapping ambient logic |
| `src/tts/sound_effects_generator.py` | Update to call provider internally (backward compat wrapper) |
| `src/tts/ambient_generator.py` | Update to call provider internally (backward compat wrapper) |
| `src/tts/tts_orchestrator.py` | Optionally inject `SoundEffectProvider` and `AmbientProvider` (default to function wrappers for backward compat) |
| `src/workflows/tts_project_gutenberg_workflow.py` | Wire new providers into orchestrator constructor |

---

## Relationship to other specs

- **US-011 (Ambient)**: Current ambient generation becomes `ElevenLabsAmbientProvider`
- **US-023 (SFX)**: Current SFX generation becomes `ElevenLabsSoundEffectProvider`
- **US-012 (Music)**: Music provider interface enables this spec's implementation
- **US-025 (Fish Audio)**: Fish Audio will implement `TTSProvider`, not the new interfaces
- **US-026 (OpenAI TTS)**: OpenAI will implement `TTSProvider` only
- **US-027 (Stable Audio)**: Stable Audio will implement `SoundEffectProvider` and `AmbientProvider`
- **US-028 (Suno)**: Suno will implement `MusicProvider`
- **TD-018 (Provider Registry)**: Depends on this spec to have interfaces to register

---

## Implementation notes

- Follow TDD: write interface tests first, then concrete implementations
- Each provider ABC lives in its own file (single responsibility)
- ElevenLabs implementations continue using `structlog.get_logger(__name__)`
- Type annotations on all public methods
- No mocks beyond the provider interface itself (at most 1 mock per test)
- Cache directory structure: `{output_dir}/sfx/`, `{output_dir}/ambient/`, `{output_dir}/music/`
