# TD-007 — Refactor AudioOrchestrator into SegmentSynthesizer and AudioAssembler

## Goal

Break down the monolithic `AudioOrchestrator` (900+ lines) into two focused, single-responsibility classes:
- **SegmentSynthesizer** — owns provider calls and feature flag gating
- **AudioAssembler** — owns silence, stitching, ambient mixing, SFX insertion
- **AudioOrchestrator** — lightweight coordinator between the two

This follows SOLID principles and makes the code testable, maintainable, and extensible.

---

## Problem

Current `AudioOrchestrator`:
- **900+ lines in a single class** — too many responsibilities
- **Mixing concerns**:
  - Segment synthesis (provider calls, feature flags, context resolution)
  - Audio assembly (silence, stitching, ambient, SFX)
  - Chapter orchestration (coordination)
- **Hard to test** — must mock both provider AND ffmpeg in single test
- **Hard to extend** — adding new audio processing steps requires modifying AudioOrchestrator
- **Feature flag enforcement spread across two layers** — emotion/voice_design/scene_context gating at lines 392-397, then ambient/SFX layers apply separately
- **Difficult to debug** — 5 concerns mixed in one class

---

## Concept

**Feature Flags and Audio Config as Constants**:

Feature flags and audio config values are defined as class constants in `AudioOrchestrator`, not passed as constructor parameters. This simplifies the interface and centralizes all configuration.

```python
# Constants defined in AudioOrchestrator (no separate constants.py needed)
class AudioOrchestrator:
    # Feature flags
    EMOTION_ENABLED = True
    VOICE_DESIGN_ENABLED = True
    SCENE_CONTEXT_ENABLED = True
    AMBIENT_ENABLED = True
    CINEMATIC_SFX_ENABLED = True

    # Audio config
    SILENCE_SAME_SPEAKER_MS = 150
    SILENCE_SPEAKER_CHANGE_MS = 400
    DEBUG = False
```

**Three Focused Classes**:

```python
class SegmentSynthesizer:
    """Owns provider calls and feature flag gating for individual segments."""
    def __init__(self, provider: TTSProvider):
        self._provider = provider

    def synthesize_segment(
        self,
        segment: Segment,
        voice_id: str,
        output_path: Path,
        context: SegmentContext,
    ) -> str:
        """
        Synthesize one segment with feature flags applied.

        Returns:
            request_id from provider
        """
        # Apply feature flags (read from AudioOrchestrator constants at import time)
        from src.audio.audio_orchestrator import AudioOrchestrator

        emotion = segment.emotion if AudioOrchestrator.EMOTION_ENABLED else None
        voice_stability = context.voice_stability if AudioOrchestrator.VOICE_DESIGN_ENABLED else None
        voice_style = context.voice_style if AudioOrchestrator.VOICE_DESIGN_ENABLED else None
        voice_speed = context.voice_speed if AudioOrchestrator.VOICE_DESIGN_ENABLED else None

        # Call provider with gated parameters
        return self._provider.synthesize(
            segment.text,
            voice_id,
            output_path,
            emotion=emotion,
            previous_text=context.previous_text,
            next_text=context.next_text,
            voice_stability=voice_stability,
            voice_style=voice_style,
            voice_speed=voice_speed,
            previous_request_ids=context.previous_request_ids,
        )


class AudioAssembler:
    """Owns audio post-processing: silence, stitching, ambient, SFX."""
    def __init__(
        self,
        output_dir: Path,
        ambient_client: Optional[Any] = None,
        sfx_client: Optional[Any] = None,
    ):
        self._output_dir = output_dir
        self._ambient_client = ambient_client
        self._sfx_client = sfx_client

    def assemble_chapter(
        self,
        segment_paths: list[Path],
        segments: list[Segment],
        scene_registry: Optional[SceneRegistry] = None,
    ) -> Path:
        """
        Post-process audio: add silence, ambient, SFX, stitch to chapter.

        Returns:
            Path to chapter.mp3
        """
        # Read constants from AudioOrchestrator
        from src.audio.audio_orchestrator import AudioOrchestrator

        # Build silence clips between segments
        silence_paths = self._build_silence_clips(
            segments,
            AudioOrchestrator.SILENCE_SAME_SPEAKER_MS,
            AudioOrchestrator.SILENCE_SPEAKER_CHANGE_MS,
        )

        # Interleave segment audio with silence
        interleaved = self._interleave_segments_and_silence(segment_paths, silence_paths)

        # Stitch to single speech file
        speech_path = self._stitch_with_ffmpeg(interleaved)

        # Apply ambient (if enabled and client provided)
        if AudioOrchestrator.AMBIENT_ENABLED and self._ambient_client:
            self._apply_ambient(speech_path, segment_paths, segments, scene_registry)

        # Insert SFX (if enabled and client provided)
        if AudioOrchestrator.CINEMATIC_SFX_ENABLED and self._sfx_client:
            self._insert_sfx(speech_path, segments)

        return speech_path


class AudioOrchestrator:
    """Lightweight coordinator: orchestrates SegmentSynthesizer and AudioAssembler."""

    # Feature flags (constants)
    EMOTION_ENABLED = True
    VOICE_DESIGN_ENABLED = True
    SCENE_CONTEXT_ENABLED = True
    AMBIENT_ENABLED = True
    CINEMATIC_SFX_ENABLED = True

    # Audio config (constants)
    SILENCE_SAME_SPEAKER_MS = 150
    SILENCE_SPEAKER_CHANGE_MS = 400
    DEBUG = False

    def __init__(
        self,
        provider: TTSProvider,
        output_dir: Path,
        ambient_client: Optional[Any] = None,
        sfx_client: Optional[Any] = None,
        scene_registry: Optional[SceneRegistry] = None,
        ffmpeg_concat_demuxer_path: Optional[Path] = None,
    ):
        self._provider = provider
        self._output_dir = output_dir
        self._ambient_client = ambient_client
        self._sfx_client = sfx_client
        self._scene_registry = scene_registry
        self._ffmpeg_concat_demuxer_path = ffmpeg_concat_demuxer_path

        self._synthesizer = SegmentSynthesizer(provider)
        self._assembler = AudioAssembler(
            output_dir,
            ambient_client=ambient_client,
            sfx_client=sfx_client,
        )

    def synthesize_chapter(
        self,
        book: Book,
        chapter_number: int,
        voice_assignment: dict[str, str],
    ) -> Path:
        """Coordinate synthesis and assembly."""
        # Step 1: Synthesize all segments
        segment_paths = self._synthesize_segments(book, chapter_number, voice_assignment)

        # Step 2: Assemble audio (silence, stitch, ambient, SFX)
        chapter_path = self._assembler.assemble_chapter(
            segment_paths,
            segments,
            scene_registry=self._scene_registry,
        )

        return chapter_path
```

---

## Acceptance Criteria

1. **SegmentSynthesizer class** (`src/audio/segment_synthesizer.py`):
   - Own all provider calls (synthesize method)
   - Own feature flag gating (emotion, voice_design, scene_context)
   - Read feature flags from `AudioOrchestrator` class constants (not constructor params)
   - Single responsibility: "synthesize one segment with flags applied"
   - Testable in isolation with single mock (provider)
   - Constructor: `__init__(self, provider: TTSProvider)` only

2. **AudioAssembler class** (`src/audio/audio_assembler.py`):
   - Own all audio post-processing:
     - Silence clip generation
     - Segment/silence interleaving
     - ffmpeg stitching
     - Ambient audio generation and mixing
     - SFX insertion into silence gaps
   - Read audio config (silence_same_speaker_ms, silence_speaker_change_ms) from `AudioOrchestrator` constants
   - Read feature flags (ambient_enabled, cinematic_sfx_enabled) from `AudioOrchestrator` constants
   - Single responsibility: "assemble chapter audio from segments"
   - Testable in isolation with mocked ffmpeg
   - Constructor: `__init__(self, output_dir: Path, ambient_client=None, sfx_client=None)` only

3. **AudioOrchestrator Constants** (`src/audio/audio_orchestrator.py`):
   - Define feature flags as class constants:
     - `EMOTION_ENABLED = True`
     - `VOICE_DESIGN_ENABLED = True`
     - `SCENE_CONTEXT_ENABLED = True`
     - `AMBIENT_ENABLED = True`
     - `CINEMATIC_SFX_ENABLED = True`
   - Define audio config as class constants:
     - `SILENCE_SAME_SPEAKER_MS = 150`
     - `SILENCE_SPEAKER_CHANGE_MS = 400`
     - `DEBUG = False`

4. **Refactored AudioOrchestrator** (`src/audio/audio_orchestrator.py`):
   - Inject SegmentSynthesizer and AudioAssembler
   - Constructor simplified: only takes `provider`, `output_dir`, optional `ambient_client`, `sfx_client`, `scene_registry`, `ffmpeg_concat_demuxer_path`
   - `synthesize_chapter()` becomes 5-10 line coordinator
   - Own only chapter-level coordination

5. **Backward Compatibility**:
   - AudioOrchestrator public interface unchanged (same signature, same behavior)
   - All existing tests pass
   - CLI and workflow integration unchanged

6. **Testability Improvements**:
   - SegmentSynthesizer tests: verify flag gating with 1 mock (provider)
   - AudioAssembler tests: verify silence/stitching/ambient/SFX with 1 mock (ffmpeg)
   - AudioOrchestrator tests: verify coordination with 2 mocks (synthesizer + assembler)
   - Each component testable independently
   - No environment-dependent tests (constants are deterministic)

7. **Code Metrics**:
   - AudioOrchestrator: ~200 lines (from 900+)
   - SegmentSynthesizer: ~150 lines
   - AudioAssembler: ~400 lines
   - Each class has single, clear responsibility

---

## Out of Scope

- Changing feature flag names or defaults
- Changing audio output or quality
- Changing CLI interface
- Changing workflow threading

---

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/audio/segment_synthesizer.py` | **NEW** — SegmentSynthesizer class (150 lines) |
| `src/audio/audio_assembler.py` | **NEW** — AudioAssembler class (400 lines) |
| `src/audio/audio_orchestrator.py` | Refactored to inject and coordinate (900 → 200 lines) |
| `src/audio/segment_synthesizer_test.py` | **NEW** — Tests for SegmentSynthesizer (~80 lines) |
| `src/audio/audio_assembler_test.py` | **NEW** — Tests for AudioAssembler (~100 lines) |
| `src/audio/audio_orchestrator_test.py` | Refactored tests, split by component |

---

## Implementation Notes

- **TDD**: Write tests for SegmentSynthesizer first, then AudioAssembler, then verify AudioOrchestrator coordination
- **Dependency Injection**: Constructor parameters flow from AudioOrchestrator → SegmentSynthesizer/AudioAssembler
- **Backward Compatibility**: AudioOrchestrator interface stays identical; internals refactored only
- **No Breaking Changes**: All existing code depending on AudioOrchestrator continues to work
- **Gradual Migration**: Extract SegmentSynthesizer, then AudioAssembler; verify tests pass between steps

---

## Success Criteria

After refactoring:
1. SegmentSynthesizer is testable with 1 mock (provider only)
2. AudioAssembler is testable with 1 mock (ffmpeg only)
3. AudioOrchestrator is testable as pure coordinator
4. Each class has single, clear responsibility
5. All 439+ existing tests pass
6. Code is easier to extend:
   - Adding new audio processing step: edit AudioAssembler, add test
   - Changing provider behavior: edit SegmentSynthesizer, add test
   - Coordinating new workflow: edit AudioOrchestrator, add test
7. Maintenance burden reduced
8. New contributors can understand each class independently

