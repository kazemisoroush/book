# US-023 — Cinematic Sound Effects (Beat-Type Design)

## Goal

Replace the current SFX implementation (which bolts `sound_effect_description` onto beats and inserts SFX into silence gaps) with a cleaner design: sound effects become first-class beats in the timeline. The AI parser detects explicit narrative sound moments and outputs SOUND_EFFECT beats with free-form descriptions. The audio builder synthesizes and stitches these beats alongside narration and dialogue, creating an immersive radio-drama experience.

## Problem

The current implementation treats sound effects as optional metadata on narration/dialogue beats. This design has several issues:

1. **Awkward model semantics** — A dialogue beat can have both `text="Hello"` and `sound_effect_description="door knock"`, which conflates two unrelated events in the timeline.
2. **SFX positioning is limited** — Sound effects are inserted into silence gaps after beats, making it impossible to put an SFX before the first beat or to precisely control timing.
3. **Code complexity** — The orchestrator has special-case logic to scan all beats for `sound_effect_description`, call the SFX generator, and splice audio into gaps. This logic doesn't belong in the orchestrator.
4. **Difficult to extend** — Adding features like overlapping SFX, adjustable SFX volume, or SFX fade-in/out requires further bolting onto the current design.

Sound effects should be beats — discrete events in the timeline, just like dialogue or narration. This makes the model clean, the code simple, and future extensions trivial.

## Concept

### New BeatType: SOUND_EFFECT

`BeatType` enum gains a new value: `SOUND_EFFECT`.

A SOUND_EFFECT beat has:
- `text: str` — short human-readable label (e.g., "door knock", "thunder crash")
- `sound_effect_detail: Optional[str]` — longer description for advanced SFX generation (e.g., "4 firm knocks on a heavy old wooden door, echoing in a stone hallway")
- `beat_type = BeatType.SOUND_EFFECT`
- `character_id = None` (SFX are not spoken by anyone)
- `scene_id` — may be set if the AI wants to link the SFX to the current scene

### AI Parser Detects SFX

The AI section parser receives an updated prompt that instructs:
- When the text explicitly mentions a diegetic sound event (a cough, a knock, thunder, etc.), output a SOUND_EFFECT beat at the position where the sound occurs.
- Evidence-based only: do NOT invent sounds. Only explicit textual mentions trigger SFX.
- Provide both a short label (`text`) and an optional detailed description (`sound_effect_detail`).

Example:

**Input text:**
> She coughed loudly, then turned to face the door. A firm knock echoed through the hall.

**AI output:**
```json
[
  {"type": "narration", "text": "She coughed loudly,", "speaker": "narrator", ...},
  {"type": "sound_effect", "text": "dry cough", "sound_effect_detail": "harsh, dry cough from a middle-aged woman"},
  {"type": "narration", "text": "then turned to face the door.", "speaker": "narrator", ...},
  {"type": "sound_effect", "text": "door knock", "sound_effect_detail": "4 firm knocks on a heavy old wooden door, echoing in a stone hallway"},
  {"type": "narration", "text": "A firm knock echoed through the hall.", "speaker": "narrator", ...}
]
```

### Audio Builder Handles SOUND_EFFECT Beats

The audio builder (currently `AudioOrchestrator` / `AudioAssembler`) treats SOUND_EFFECT beats like any other beat:

1. Collect all beats in chapter order (narration, dialogue, SOUND_EFFECT).
2. For each SOUND_EFFECT beat:
   - Call `sound_effect_provider.generate(beat.sound_effect_detail or beat.text, output_path, duration_seconds=2.0)`
   - If generation fails, skip the beat (log warning, no error).
3. Stitch all beat audio files (speech + SFX) in timeline order with appropriate silence gaps.

SFX beats appear in the concat list at the exact position where they occur in the timeline — no special-case gap insertion logic.

### Remove Old Implementation

This spec **completely replaces** the existing SFX implementation:

1. **Remove `sound_effect_description` field** from `Beat` in `src/domain/models.py`.
2. **Remove old SFX insertion logic** from `src/audio/audio_orchestrator.py` (the code that scans beats for `sound_effect_description` and calls `sound_effects_generator.py`).
3. **Delete `src/audio/sound_effects_generator.py`** (the standalone SFX generator module is no longer used; `SoundEffectProvider` interface replaces it).
4. **Remove `sound_effect_description` prompt instructions** from `src/parsers/prompt_builder.py`.
5. **Remove `sound_effect_description` parsing logic** from `src/parsers/ai_section_parser.py`.
6. **Remove all tests** for the old implementation (grep for `sound_effect_description` in test files).

The `SoundEffectProvider` interface (already exists) remains unchanged. Implementations (`ElevenLabsSoundEffectProvider`, `StableAudioSoundEffectProvider`) are reused as-is.

## Acceptance criteria

1. `BeatType` enum gains `SOUND_EFFECT = "sound_effect"` value in `src/domain/models.py`.

2. `Beat` dataclass gains new field `sound_effect_detail: Optional[str] = None` in `src/domain/models.py`.

3. `Beat.sound_effect_description` field is **removed** from `src/domain/models.py`.

4. AI parser prompt (in `src/parsers/prompt_builder.py`) is updated:
   - Remove `sound_effect_description` instruction.
   - Add instruction: "When the text explicitly mentions a diegetic sound event, output a SOUND_EFFECT beat with `type: 'sound_effect'`, `text: <short label>`, and optional `sound_effect_detail: <detailed description>`. Evidence-based only — do NOT invent sounds."
   - Example output includes at least one SOUND_EFFECT beat.

5. AI parser (`src/parsers/ai_section_parser.py`) parses SOUND_EFFECT beats:
   - Recognizes `type: "sound_effect"` in AI response.
   - Creates `Beat(text=..., beat_type=BeatType.SOUND_EFFECT, sound_effect_detail=...)`.
   - Sets `character_id=None` for SOUND_EFFECT beats.
   - Removes old `sound_effect_description` parsing code.

6. Audio builder (`src/audio/audio_orchestrator.py` or extracted `AudioAssembler`) synthesizes SOUND_EFFECT beats:
   - During beat iteration, when `beat.beat_type == BeatType.SOUND_EFFECT`:
     - Call `sound_effect_provider.generate(beat.sound_effect_detail or beat.text, output_path, duration_seconds=2.0)`.
     - On failure, log warning and skip the beat (no crash).
   - SOUND_EFFECT beats appear in the concat list at their timeline position (no special gap insertion).

7. Old SFX code is removed:
   - `src/audio/sound_effects_generator.py` is deleted.
   - All `sound_effect_description` code in `src/audio/audio_orchestrator.py` is removed.
   - Old prompt instructions in `src/parsers/prompt_builder.py` are removed.
   - Old parsing logic in `src/parsers/ai_section_parser.py` is removed.

8. `Book.to_dict()` and `Book.from_dict()` round-trip SOUND_EFFECT beats correctly:
   - `beat_type: "sound_effect"` serializes/deserializes as `BeatType.SOUND_EFFECT`.
   - `sound_effect_detail` field is preserved.

9. Feature flag `cinematic_sfx_enabled` in `FeatureFlags` continues to work:
   - When `False`, SOUND_EFFECT beats are skipped during audio synthesis (no calls to `sound_effect_provider.generate`).
   - When `True`, SOUND_EFFECT beats are synthesized and stitched.

10. All existing tests pass (after updating tests that reference the old `sound_effect_description` field).

11. New unit tests cover:
    - `BeatType.SOUND_EFFECT` is a valid enum value.
    - AI parser creates SOUND_EFFECT beats with `text` and `sound_effect_detail`.
    - Audio builder synthesizes SOUND_EFFECT beats via `SoundEffectProvider`.
    - SOUND_EFFECT beats are skipped when `cinematic_sfx_enabled=False`.
    - `Book.to_dict()` and `Book.from_dict()` preserve SOUND_EFFECT beats.

## Out of scope

- Overlapping SFX (multiple SFX playing simultaneously) — future work.
- Per-SFX volume control — SFX use default provider volume.
- SFX fade-in/fade-out — provider handles this internally if supported.
- SFX timing offsets (e.g., "start 0.5s into the silence gap") — SFX play at their exact timeline position.
- Retroactive SFX insertion (adding SFX to already-cached chapters) — user must `--reparse` to regenerate.
- AI confidence scoring for SFX detection — all explicit mentions are marked.

## Key design decisions

### Why beats, not metadata?

A sound effect is a discrete event in the timeline. Modeling it as a beat makes the domain model consistent: every event (narration, dialogue, SFX) is a beat. This simplifies serialization, iteration, and extension.

### Why two description fields (text + detail)?

- `text` is required — a short human-readable label for logs, debugging, and UI (e.g., "door knock").
- `sound_effect_detail` is optional — a longer, more specific prompt for advanced SFX generation (e.g., "4 firm knocks on a heavy old wooden door, echoing in a stone hallway"). Providers can use whichever field they prefer; the audio builder tries `detail` first, falls back to `text`.

### Evidence-based detection only

The AI must NOT invent sounds. Only explicit textual mentions trigger SFX. This keeps the experience grounded and trustworthy — readers feel the SFX are "real" to the narrative, not hallucinated.

### Graceful provider failures

If `SoundEffectProvider.generate()` returns `None`, the builder logs a warning and skips the beat. The chapter audio is still produced; it just lacks that particular SFX. This matches the existing ambient and TTS error-handling pattern.

### Remove old code entirely

No backward compatibility for `sound_effect_description`. The old field is removed from the model, all parsing code is deleted, and tests are rewritten. This spec is a clean break.

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `SOUND_EFFECT` to `BeatType` enum; add `sound_effect_detail: Optional[str] = None` to `Beat`; remove `sound_effect_description` field |
| `src/parsers/prompt_builder.py` | Remove old `sound_effect_description` prompt; add SOUND_EFFECT beat instruction with examples |
| `src/parsers/ai_section_parser.py` | Parse `type: "sound_effect"` from AI response; create SOUND_EFFECT beats; remove old `sound_effect_description` parsing |
| `src/audio/audio_orchestrator.py` | Remove old SFX insertion logic (gap scanning, `sound_effects_generator` calls) |
| `src/audio/audio_assembler.py` | Add SOUND_EFFECT synthesis logic (call `sound_effect_provider.generate` during beat iteration) |
| `src/audio/sound_effects_generator.py` | **Delete file** — replaced by `SoundEffectProvider` interface |
| `src/parsers/ai_section_parser_test.py` | Remove old `sound_effect_description` tests; add SOUND_EFFECT beat parsing tests |
| `src/audio/audio_orchestrator_test.py` | Remove old SFX insertion tests; add SOUND_EFFECT synthesis tests |
| `src/domain/models_test.py` | Add SOUND_EFFECT beat round-trip serialization tests |

## Relationship to other specs

- **US-011 (Ambient)**: Ambient provides recessive environmental backdrop; SFX are foreground events. No interaction.
- **US-016 (Inter-Beat Silence)**: Silence gaps still exist between all beats (including SOUND_EFFECT). Silence calculation logic is unchanged.
- **US-024 (Audio Provider Separation)**: `SoundEffectProvider` interface is already separated. This spec uses it as-is.
- **TD-007 (AudioOrchestrator Refactor)**: `AudioAssembler` is the right place for SOUND_EFFECT synthesis logic (beat iteration and stitching). If `AudioAssembler` is not yet fully extracted, this spec may need to modify `AudioOrchestrator` directly.

## Implementation notes

1. **TDD flow**:
   - Write failing test for `BeatType.SOUND_EFFECT` enum value.
   - Write failing test for AI parser creating SOUND_EFFECT beats.
   - Write failing test for audio builder synthesizing SOUND_EFFECT beats.
   - Implement each in turn until all tests pass.

2. **Prompt engineering**: The AI prompt must clearly distinguish between:
   - Explicit sound mentions (cough, knock, thunder) → SOUND_EFFECT beat.
   - Implicit/inferred sounds (footsteps because someone "walked") → NO SOUND_EFFECT beat.
   - Provide 2-3 positive and 2-3 negative examples in the prompt.

3. **Migration path**: There is no migration path for existing cached books with `sound_effect_description`. Users must `--reparse` to regenerate with the new design. Add a note in the spec (this section) and in commit messages.

4. **Feature flag enforcement**: The `cinematic_sfx_enabled` flag should gate SOUND_EFFECT synthesis in the audio builder, not in the AI parser. The AI always outputs SOUND_EFFECT beats (when detected); the flag controls whether they're synthesized.

5. **Type annotations**: All new functions and methods must have full type annotations (mypy strict mode).

6. **Structured logging**: Use `structlog.get_logger(__name__)` in all modified modules. Log SFX synthesis events at `debug` level, failures at `warning` level.

7. **Test quality**: At most 1 mock per test. Arrange / Act / Assert structure. No constructor-assertion tests.
