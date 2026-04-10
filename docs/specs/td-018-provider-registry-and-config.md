# TD-018 — Provider Registry and Config

## Goal

Create a centralized provider registry and configuration system that allows users to select which audio provider to use for each concern (TTS, SFX, ambient, music) via environment variables. The registry validates that selected providers support required features, automatically disables unsupported features via `FeatureFlags`, and constructs provider instances with correct dependencies.

---

## Problem

After US-024 through US-028, the project has multiple providers for each audio concern:
- **TTS**: ElevenLabs, Fish Audio, OpenAI (with fallback wrapper)
- **SFX**: ElevenLabs, Stable Audio
- **Ambient**: ElevenLabs, Stable Audio
- **Music**: Suno (and future ElevenLabs)

Currently, no mechanism exists to:

1. **Select providers at runtime** — provider instances are hardcoded in `TTSProjectGutenbergWorkflow`
2. **Validate feature compatibility** — if Fish Audio is selected (no prosody context), emotion/context features should auto-disable
3. **Construct fallback wrappers** — no way to configure "use Fish Audio with OpenAI fallback"
4. **Centralize API keys** — each provider pulls keys from `Config`; no validation that required keys exist before workflow starts

Users need a simple config interface:
```bash
TTS_PROVIDER=fish_audio
TTS_FALLBACK_PROVIDER=openai
SFX_PROVIDER=stable_audio
AMBIENT_PROVIDER=elevenlabs
MUSIC_PROVIDER=suno
```

The system should validate these settings, construct providers, and adjust feature flags automatically.

---

## Concept

### 1. Provider Registry

A factory that maps provider names to concrete classes:

```python
class ProviderRegistry:
    """Registry of available audio providers."""

    # Class-level registries
    _tts_providers: dict[str, type[TTSProvider]] = {}
    _sfx_providers: dict[str, type[SoundEffectProvider]] = {}
    _ambient_providers: dict[str, type[AmbientProvider]] = {}
    _music_providers: dict[str, type[MusicProvider]] = {}

    @classmethod
    def register_tts(cls, name: str, provider_class: type[TTSProvider]) -> None:
        """Register a TTS provider."""

    @classmethod
    def create_tts_provider(cls, name: str, config: Config) -> TTSProvider:
        """Create a TTS provider instance by name."""

    # Similar methods for SFX, ambient, music...
```

**Registration** happens at module import time (or via a registration function called at startup):
```python
# In src/tts/__init__.py or similar
ProviderRegistry.register_tts("elevenlabs", ElevenLabsProvider)
ProviderRegistry.register_tts("fish_audio", FishAudioTTSProvider)
ProviderRegistry.register_tts("openai", OpenAITTSProvider)
# ...
```

### 2. Provider Configuration

Extend `Config` dataclass with provider selection fields:

```python
@dataclass
class Config:
    # ... existing fields ...

    # Provider selection
    tts_provider: str = "elevenlabs"
    tts_fallback_provider: Optional[str] = None
    sfx_provider: str = "elevenlabs"
    ambient_provider: str = "elevenlabs"
    music_provider: str = "suno"

    # API keys (already exist, but now required based on selected providers)
    elevenlabs_api_key: Optional[str] = None
    fish_audio_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    stability_api_key: Optional[str] = None
    suno_api_key: Optional[str] = None
```

Loaded from environment variables:
```python
@classmethod
def from_env(cls) -> 'Config':
    return cls(
        # ... existing fields ...
        tts_provider=os.getenv("TTS_PROVIDER", "elevenlabs"),
        tts_fallback_provider=os.getenv("TTS_FALLBACK_PROVIDER"),
        sfx_provider=os.getenv("SFX_PROVIDER", "elevenlabs"),
        ambient_provider=os.getenv("AMBIENT_PROVIDER", "elevenlabs"),
        music_provider=os.getenv("MUSIC_PROVIDER", "suno"),
        # ... API keys ...
    )
```

### 3. Feature Flag Adjustment

Providers declare their capabilities:

```python
class ProviderCapabilities:
    """Describes what features a provider supports."""
    supports_emotion: bool = False
    supports_prosody_context: bool = False
    supports_voice_design: bool = False
    supports_scene_context: bool = False
```

Each provider class has a class-level `CAPABILITIES` attribute:
```python
class ElevenLabsProvider(TTSProvider):
    CAPABILITIES = ProviderCapabilities(
        supports_emotion=True,
        supports_prosody_context=True,
        supports_voice_design=True,
        supports_scene_context=True,
    )

class FishAudioTTSProvider(TTSProvider):
    CAPABILITIES = ProviderCapabilities(
        supports_emotion=True,  # Fish Audio supports emotion
        supports_prosody_context=False,  # No previous_text/next_text
        supports_voice_design=False,  # No voice design API
        supports_scene_context=True,  # Supports voice modifiers
    )

class OpenAITTSProvider(TTSProvider):
    CAPABILITIES = ProviderCapabilities(
        # All False — OpenAI TTS is basic
    )
```

The registry uses these capabilities to adjust `FeatureFlags`:

```python
def adjust_feature_flags(
    provider: TTSProvider,
    flags: FeatureFlags,
) -> FeatureFlags:
    """Disable features not supported by the provider."""
    caps = provider.CAPABILITIES
    return FeatureFlags(
        emotion_enabled=flags.emotion_enabled and caps.supports_emotion,
        voice_design_enabled=flags.voice_design_enabled and caps.supports_voice_design,
        scene_context_enabled=flags.scene_context_enabled and caps.supports_scene_context,
        ambient_enabled=flags.ambient_enabled,  # SFX/ambient providers checked separately
        cinematic_sfx_enabled=flags.cinematic_sfx_enabled,
    )
```

### 4. Validation

`Config.validate()` checks:
- Selected provider names exist in the registry
- Required API keys are present for selected providers
- If `tts_fallback_provider` is set, both primary and fallback keys exist

Example validation:
```python
def validate(self) -> None:
    # ... existing validation ...

    # Validate TTS provider
    if self.tts_provider not in ProviderRegistry.list_tts_providers():
        logger.error("invalid_tts_provider", provider=self.tts_provider)
        sys.exit(1)

    # Validate API keys for selected providers
    if self.tts_provider == "elevenlabs" and not self.elevenlabs_api_key:
        logger.error("missing_api_key", provider="elevenlabs", env_var="ELEVENLABS_API_KEY")
        sys.exit(1)

    # Similar checks for other providers...
```

### 5. Workflow Integration

`TTSProjectGutenbergWorkflow` uses the registry to construct providers:

```python
# Before (hardcoded):
tts_provider = ElevenLabsProvider(api_key=config.elevenlabs_api_key)

# After (registry):
tts_provider = ProviderRegistry.create_tts_provider(
    config.tts_provider,
    config,
)

# Fallback wrapper (if configured):
if config.tts_fallback_provider:
    fallback = ProviderRegistry.create_tts_provider(
        config.tts_fallback_provider,
        config,
    )
    tts_provider = FallbackTTSProvider(tts_provider, fallback)

# Adjust feature flags based on provider capabilities
feature_flags = ProviderRegistry.adjust_feature_flags(
    tts_provider,
    config.feature_flags,
)
```

---

## Acceptance criteria

1. New `src/tts/provider_registry.py` module contains `ProviderRegistry` class with:
   - `register_tts(name, provider_class)` / `register_sfx(...)` / `register_ambient(...)` / `register_music(...)`
   - `create_tts_provider(name, config)` / `create_sfx_provider(...)` / `create_ambient_provider(...)` / `create_music_provider(...)`
   - `list_tts_providers()` / `list_sfx_providers()` / `list_ambient_providers()` / `list_music_providers()` (returns list of registered names)

2. New `src/tts/provider_capabilities.py` module contains `ProviderCapabilities` dataclass

3. Each provider class gains a class-level `CAPABILITIES` attribute declaring its support for features

4. `ProviderRegistry.adjust_feature_flags(provider, flags) -> FeatureFlags` disables unsupported features

5. `Config` gains provider selection fields:
   - `tts_provider: str` (default `"elevenlabs"`)
   - `tts_fallback_provider: Optional[str]` (default `None`)
   - `sfx_provider: str` (default `"elevenlabs"`)
   - `ambient_provider: str` (default `"elevenlabs"`)
   - `music_provider: str` (default `"suno"`)

6. `Config` gains API key fields for new providers:
   - `fish_audio_api_key: Optional[str]`
   - `stability_api_key: Optional[str]`
   - `suno_api_key: Optional[str]`
   - `openai_api_key: Optional[str]`

7. `Config.from_env()` loads provider selections from environment variables:
   - `TTS_PROVIDER`, `TTS_FALLBACK_PROVIDER`, `SFX_PROVIDER`, `AMBIENT_PROVIDER`, `MUSIC_PROVIDER`
   - `FISH_AUDIO_API_KEY`, `STABILITY_API_KEY`, `SUNO_API_KEY`, `OPENAI_API_KEY`

8. `Config.validate()` checks:
   - Provider names exist in registry (exits with error if not)
   - Required API keys present for selected providers (exits with error if missing)
   - Fallback provider key exists if `tts_fallback_provider` is set

9. `TTSProjectGutenbergWorkflow` uses registry to construct providers:
   - TTS provider (with optional fallback wrapper)
   - SFX provider (passed to orchestrator)
   - Ambient provider (passed to orchestrator)
   - Music provider (if music feature is implemented)

10. Feature flags are adjusted based on TTS provider capabilities before passing to orchestrator

11. All providers are registered at startup (in `src/tts/__init__.py` or a dedicated registration module)

12. New unit tests cover:
    - Provider registration and retrieval
    - Provider creation with correct API keys
    - Fallback wrapper construction when `tts_fallback_provider` is set
    - Feature flag adjustment (disable unsupported features)
    - Config validation (invalid provider name, missing API key)
    - `list_*_providers()` returns correct registered names

13. All existing tests continue to pass

---

## Out of scope

- Dynamic provider loading (all providers compiled into binary; no plugin system)
- Provider auto-discovery (explicit registration required)
- Per-chapter provider switching (one provider per concern per run)
- Cost estimation or quota tracking across providers
- Provider health checks or availability testing
- Voice mapping between providers (e.g., auto-map ElevenLabs voices to OpenAI voices)
- Removing environment variable support (CLI args remain but env vars are the primary config mechanism)

---

## Key design decisions

### Why class-level registry instead of instance-based?

Providers are stateless factories (given API key + config, produce audio). A class-level registry is simpler and avoids singleton boilerplate. Registration happens once at startup; lookups are thread-safe (reading from a dict).

### Why ProviderCapabilities instead of runtime capability queries?

Capabilities are static properties of a provider class. Declaring them at the class level allows:
- Compile-time registration
- Clear documentation (capabilities visible in code)
- No runtime overhead (no need to instantiate provider to check capabilities)

Runtime queries would require instantiating each provider (expensive, requires API keys) just to check capabilities.

### Why adjust feature flags automatically instead of erroring?

User experience: if a user switches from ElevenLabs to Fish Audio, they shouldn't have to manually disable prosody context features. The system should "do the right thing" and disable unsupported features with a warning log.

Explicit errors would be noisy and frustrating ("Feature X not supported by provider Y" on every run).

### Why Config.validate() instead of validation at provider construction?

Fail fast. Validation at startup (before expensive parsing/AI work) provides clear error messages and prevents wasted work. Validation at provider construction would happen mid-workflow, harder to debug.

### Why allow providers to remain backward-compatible with convenience functions?

Incremental migration. Existing code (e.g., `get_sound_effect()`) can continue to work while new code uses the provider abstraction. Over time, convenience functions can become thin wrappers around providers, eventually deprecated if desired.

No flag day where all code must switch at once.

### Why not support per-chapter provider selection?

Complexity vs. value. Most users will pick one provider and stick with it for the entire book. Per-chapter switching would require:
- Provider state in `Chapter` objects
- Workflow logic to switch providers mid-book
- Inconsistent audio characteristics (jarring for listeners)

If a compelling use case emerges, this can be added later without breaking the registry pattern.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/provider_registry.py` | **New module** — `ProviderRegistry` class with registration and factory methods |
| `src/tts/provider_capabilities.py` | **New module** — `ProviderCapabilities` dataclass |
| `src/tts/elevenlabs_provider.py` | Add `CAPABILITIES` class attribute |
| `src/tts/fish_audio_provider.py` | Add `CAPABILITIES` class attribute |
| `src/tts/openai_tts_provider.py` | Add `CAPABILITIES` class attribute |
| `src/tts/elevenlabs_sound_effect_provider.py` | Add `CAPABILITIES` class attribute (if needed) |
| `src/tts/stable_audio_sound_effect_provider.py` | Add `CAPABILITIES` class attribute (if needed) |
| `src/tts/elevenlabs_ambient_provider.py` | Add `CAPABILITIES` class attribute (if needed) |
| `src/tts/stable_audio_ambient_provider.py` | Add `CAPABILITIES` class attribute (if needed) |
| `src/tts/suno_music_provider.py` | Add `CAPABILITIES` class attribute (if needed) |
| `src/tts/__init__.py` | Register all providers at module import |
| `src/config/config.py` | Add provider selection fields and API key fields |
| `src/workflows/tts_project_gutenberg_workflow.py` | Use registry to construct providers; adjust feature flags |

---

## Relationship to other specs

- **US-024 (Interface Separation)**: Registry manages providers implementing these interfaces
- **US-025 (Fish Audio)**: Fish Audio is registered and selectable via `TTS_PROVIDER=fish_audio`
- **US-026 (OpenAI TTS Fallback)**: OpenAI is registered; fallback wrapper constructed when `TTS_FALLBACK_PROVIDER=openai`
- **US-027 (Stable Audio)**: Stable Audio SFX/ambient registered and selectable
- **US-028 (Suno Music)**: Suno music registered and selectable
- **TD-004 (Standardize Feature Flags)**: Registry adjusts existing `FeatureFlags` based on provider capabilities

---

## Implementation notes

- Follow existing patterns from `FeatureFlags` for config loading
- Type annotations on all public methods
- Structured logging (`structlog.get_logger(__name__)`)
- TDD: write tests first (mock providers for registry tests)
- No mocks beyond provider class mocks (at most 1 mock per test)
- Provider registration should be idempotent (calling `register_tts(name, cls)` twice is safe)
- `create_*_provider()` should raise `ValueError` if provider name not registered
- Log at info level when feature flags are adjusted: `"feature_flag_adjusted", feature="emotion_enabled", reason="provider_does_not_support_emotion"`
