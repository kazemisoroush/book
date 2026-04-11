# US-023 — Cinematic Sound Effects (Segment-Type Design)

## Goal

Replace the current SFX implementation (which bolts `sound_effect_description` onto segments and inserts SFX into silence gaps) with a cleaner design: sound effects become first-class segments in the timeline. The AI parser detects explicit narrative sound moments and outputs SOUND_EFFECT segments with free-form descriptions. The audio builder synthesizes and stitches these segments alongside narration and dialogue, creating an immersive radio-drama experience.

## Problem

The current implementation treats sound effects as optional metadata on narration/dialogue segments. This design has several issues:

1. **Awkward model semantics** — A dialogue segment can have both `text="Hello"` and `sound_effect_description="door knock"`, which conflates two unrelated events in the timeline.
2. **SFX positioning is limited** — Sound effects are inserted into silence gaps after segments, making it impossible to put an SFX before the first segment or to precisely control timing.
3. **Code complexity** — The orchestrator has special-case logic to scan all segments for `sound_effect_description`, call the SFX generator, and splice audio into gaps. This logic doesn't belong in the orchestrator.
4. **Difficult to extend** — Adding features like overlapping SFX, adjustable SFX volume, or SFX fade-in/out requires further bolting onto the current design.

Sound effects should be segments — discrete events in the timeline, just like dialogue or narration. This makes the model clean, the code simple, and future extensions trivial.

## Concept

### New SegmentType: SOUND_EFFECT

`SegmentType` enum gains a new value: `SOUND_EFFECT`.

A SOUND_EFFECT segment has:
- `text: str` — short human-readable label (e.g., "door knock", "thunder crash")
- `sound_effect_detail: Optional[str]` — longer description for advanced SFX generation (e.g., "4 firm knocks on a heavy old wooden door, echoing in a stone hallway")
- `segment_type = SegmentType.SOUND_EFFECT`
- `character_id = None` (SFX are not spoken by anyone)
- `scene_id` — may be set if the AI wants to link the SFX to the current scene

### AI Parser Detects SFX

The AI section parser receives an updated prompt that instructs:
- When the text explicitly mentions a diegetic sound event (a cough, a knock, thunder, etc.), output a SOUND_EFFECT segment at the position where the sound occurs.
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

### Audio Builder Handles SOUND_EFFECT Segments

The audio builder (currently `TTSOrchestrator` / `AudioAssembler`) treats SOUND_EFFECT segments like any other segment:

1. Collect all segments in chapter order (narration, dialogue, SOUND_EFFECT).
2. For each SOUND_EFFECT segment:
   - Call `sound_effect_provider.generate(segment.sound_effect_detail or segment.text, output_path, duration_seconds=2.0)`
   - If generation fails, skip the segment (log warning, no error).
3. Stitch all segment audio files (speech + SFX) in timeline order with appropriate silence gaps.

SFX segments appear in the concat list at the exact position where they occur in the timeline — no special-case gap insertion logic.

### Remove Old Implementation

This spec **completely replaces** the existing SFX implementation:

1. **Remove `sound_effect_description` field** from `Segment` in `src/domain/models.py`.
2. **Remove old SFX insertion logic** from `src/tts/tts_orchestrator.py` (the code that scans segments for `sound_effect_description` and calls `sound_effects_generator.py`).
3. **Delete `src/tts/sound_effects_generator.py`** (the standalone SFX generator module is no longer used; `SoundEffectProvider` interface replaces it).
4. **Remove `sound_effect_description` prompt instructions** from `src/parsers/prompt_builder.py`.
5. **Remove `sound_effect_description` parsing logic** from `src/parsers/ai_section_parser.py`.
6. **Remove all tests** for the old implementation (grep for `sound_effect_description` in test files).

The `SoundEffectProvider` interface (already exists) remains unchanged. Implementations (`ElevenLabsSoundEffectProvider`, `StableAudioSoundEffectProvider`) are reused as-is.

## Acceptance criteria

1. `SegmentType` enum gains `SOUND_EFFECT = "sound_effect"` value in `src/domain/models.py`.

2. `Segment` dataclass gains new field `sound_effect_detail: Optional[str] = None` in `src/domain/models.py`.

3. `Segment.sound_effect_description` field is **removed** from `src/domain/models.py`.

4. AI parser prompt (in `src/parsers/prompt_builder.py`) is updated:
   - Remove `sound_effect_description` instruction.
   - Add instruction: "When the text explicitly mentions a diegetic sound event, output a SOUND_EFFECT segment with `type: 'sound_effect'`, `text: <short label>`, and optional `sound_effect_detail: <detailed description>`. Evidence-based only — do NOT invent sounds."
   - Example output includes at least one SOUND_EFFECT segment.

5. AI parser (`src/parsers/ai_section_parser.py`) parses SOUND_EFFECT segments:
   - Recognizes `type: "sound_effect"` in AI response.
   - Creates `Segment(text=..., segment_type=SegmentType.SOUND_EFFECT, sound_effect_detail=...)`.
   - Sets `character_id=None` for SOUND_EFFECT segments.
   - Removes old `sound_effect_description` parsing code.

6. Audio builder (`src/tts/tts_orchestrator.py` or extracted `AudioAssembler`) synthesizes SOUND_EFFECT segments:
   - During segment iteration, when `segment.segment_type == SegmentType.SOUND_EFFECT`:
     - Call `sound_effect_provider.generate(segment.sound_effect_detail or segment.text, output_path, duration_seconds=2.0)`.
     - On failure, log warning and skip the segment (no crash).
   - SOUND_EFFECT segments appear in the concat list at their timeline position (no special gap insertion).

7. Old SFX code is removed:
   - `src/tts/sound_effects_generator.py` is deleted.
   - All `sound_effect_description` code in `src/tts/tts_orchestrator.py` is removed.
   - Old prompt instructions in `src/parsers/prompt_builder.py` are removed.
   - Old parsing logic in `src/parsers/ai_section_parser.py` is removed.

8. `Book.to_dict()` and `Book.from_dict()` round-trip SOUND_EFFECT segments correctly:
   - `segment_type: "sound_effect"` serializes/deserializes as `SegmentType.SOUND_EFFECT`.
   - `sound_effect_detail` field is preserved.

9. Feature flag `cinematic_sfx_enabled` in `FeatureFlags` continues to work:
   - When `False`, SOUND_EFFECT segments are skipped during audio synthesis (no calls to `sound_effect_provider.generate`).
   - When `True`, SOUND_EFFECT segments are synthesized and stitched.

10. All existing tests pass (after updating tests that reference the old `sound_effect_description` field).

11. New unit tests cover:
    - `SegmentType.SOUND_EFFECT` is a valid enum value.
    - AI parser creates SOUND_EFFECT segments with `text` and `sound_effect_detail`.
    - Audio builder synthesizes SOUND_EFFECT segments via `SoundEffectProvider`.
    - SOUND_EFFECT segments are skipped when `cinematic_sfx_enabled=False`.
    - `Book.to_dict()` and `Book.from_dict()` preserve SOUND_EFFECT segments.

## Out of scope

- Overlapping SFX (multiple SFX playing simultaneously) — future work.
- Per-SFX volume control — SFX use default provider volume.
- SFX fade-in/fade-out — provider handles this internally if supported.
- SFX timing offsets (e.g., "start 0.5s into the silence gap") — SFX play at their exact timeline position.
- Retroactive SFX insertion (adding SFX to already-cached chapters) — user must `--reparse` to regenerate.
- AI confidence scoring for SFX detection — all explicit mentions are marked.

## Key design decisions

### Why segments, not metadata?

A sound effect is a discrete event in the timeline. Modeling it as a segment makes the domain model consistent: every event (narration, dialogue, SFX) is a segment. This simplifies serialization, iteration, and extension.

### Why two description fields (text + detail)?

- `text` is required — a short human-readable label for logs, debugging, and UI (e.g., "door knock").
- `sound_effect_detail` is optional — a longer, more specific prompt for advanced SFX generation (e.g., "4 firm knocks on a heavy old wooden door, echoing in a stone hallway"). Providers can use whichever field they prefer; the audio builder tries `detail` first, falls back to `text`.

### Evidence-based detection only

The AI must NOT invent sounds. Only explicit textual mentions trigger SFX. This keeps the experience grounded and trustworthy — readers feel the SFX are "real" to the narrative, not hallucinated.

### Graceful provider failures

If `SoundEffectProvider.generate()` returns `None`, the builder logs a warning and skips the segment. The chapter audio is still produced; it just lacks that particular SFX. This matches the existing ambient and TTS error-handling pattern.

### Remove old code entirely

No backward compatibility for `sound_effect_description`. The old field is removed from the model, all parsing code is deleted, and tests are rewritten. This spec is a clean break.

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `SOUND_EFFECT` to `SegmentType` enum; add `sound_effect_detail: Optional[str] = None` to `Segment`; remove `sound_effect_description` field |
| `src/parsers/prompt_builder.py` | Remove old `sound_effect_description` prompt; add SOUND_EFFECT segment instruction with examples |
| `src/parsers/ai_section_parser.py` | Parse `type: "sound_effect"` from AI response; create SOUND_EFFECT segments; remove old `sound_effect_description` parsing |
| `src/tts/tts_orchestrator.py` | Remove old SFX insertion logic (gap scanning, `sound_effects_generator` calls) |
| `src/tts/audio_assembler.py` | Add SOUND_EFFECT synthesis logic (call `sound_effect_provider.generate` during segment iteration) |
| `src/tts/sound_effects_generator.py` | **Delete file** — replaced by `SoundEffectProvider` interface |
| `src/parsers/ai_section_parser_test.py` | Remove old `sound_effect_description` tests; add SOUND_EFFECT segment parsing tests |
| `src/tts/tts_orchestrator_test.py` | Remove old SFX insertion tests; add SOUND_EFFECT synthesis tests |
| `src/domain/models_test.py` | Add SOUND_EFFECT segment round-trip serialization tests |

## Relationship to other specs

- **US-011 (Ambient)**: Ambient provides recessive environmental backdrop; SFX are foreground events. No interaction.
- **US-016 (Inter-Segment Silence)**: Silence gaps still exist between all segments (including SOUND_EFFECT). Silence calculation logic is unchanged.
- **US-024 (Audio Provider Separation)**: `SoundEffectProvider` interface is already separated. This spec uses it as-is.
- **TD-007 (TTSOrchestrator Refactor)**: `AudioAssembler` is the right place for SOUND_EFFECT synthesis logic (segment iteration and stitching). If `AudioAssembler` is not yet fully extracted, this spec may need to modify `TTSOrchestrator` directly.

## Implementation notes

1. **TDD flow**:
   - Write failing test for `SegmentType.SOUND_EFFECT` enum value.
   - Write failing test for AI parser creating SOUND_EFFECT segments.
   - Write failing test for audio builder synthesizing SOUND_EFFECT segments.
   - Implement each in turn until all tests pass.

2. **Prompt engineering**: The AI prompt must clearly distinguish between:
   - Explicit sound mentions (cough, knock, thunder) → SOUND_EFFECT segment.
   - Implicit/inferred sounds (footsteps because someone "walked") → NO SOUND_EFFECT segment.
   - Provide 2-3 positive and 2-3 negative examples in the prompt.

3. **Migration path**: There is no migration path for existing cached books with `sound_effect_description`. Users must `--reparse` to regenerate with the new design. Add a note in the spec (this section) and in commit messages.

4. **Feature flag enforcement**: The `cinematic_sfx_enabled` flag should gate SOUND_EFFECT synthesis in the audio builder, not in the AI parser. The AI always outputs SOUND_EFFECT segments (when detected); the flag controls whether they're synthesized.

5. **Type annotations**: All new functions and methods must have full type annotations (mypy strict mode).

6. **Structured logging**: Use `structlog.get_logger(__name__)` in all modified modules. Log SFX synthesis events at `debug` level, failures at `warning` level.

7. **Test quality**: At most 1 mock per test. Arrange / Act / Assert structure. No constructor-assertion tests.
