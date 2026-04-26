# US-035 — Narrator Emotion

## Problem

The narrator voice is currently forced to emotional neutrality. The
section-parser prompt instructs: *"Use 'neutral' for narration..."*, and the
voice-settings tables pin narration at `stability=0.65`, `style=0.05` —
the most stable, least expressive corner of the parameter space.

Professional audiobook narration (e.g. Jim Dale / Stephen Fry on *Harry
Potter*) does not do this. Narrators operate in a **narrower emotional band
than characters**, but the band is not zero. A competent narrator sounds
genuinely sorrowful at a funeral and genuinely tense during a chase, without
crossing into theatrical character-acting.

The user's goal is audiobook output comparable to professional narration.
A flat narrator is the single largest gap versus that benchmark.

## Proposed Solution

The narrator's voice settings are derived deterministically from the current
`StoryMood` (US-034) via a fixed mapping table, clamped to a **narrator band**
that is narrower than the range available to characters.

**Narrator band (hard clamps).**

- `stability ∈ [0.45, 0.70]`
- `style    ∈ [0.00, 0.25]`
- `speed    ∈ [0.90, 1.05]`

Characters remain free to use the full range. The narrator band prevents the
narrator from sounding like a character actor.

**Mood → narrator voice mapping** (deterministic lookup table, tunable):

| StoryMood       | stability | style | speed |
|---|---|---|---|
| neutral         | 0.65 | 0.05 | 1.00 |
| tender          | 0.55 | 0.15 | 0.95 |
| wistful         | 0.55 | 0.15 | 0.92 |
| grief           | 0.50 | 0.20 | 0.90 |
| tense_pursuit   | 0.45 | 0.20 | 1.05 |
| dread           | 0.50 | 0.15 | 0.92 |
| terror          | 0.45 | 0.25 | 1.05 |
| triumph         | 0.50 | 0.20 | 1.00 |
| comic           | 0.50 | 0.20 | 1.00 |
| awe             | 0.55 | 0.15 | 0.95 |
| anger           | 0.45 | 0.25 | 1.00 |
| bittersweet     | 0.55 | 0.15 | 0.95 |
| mystery         | 0.55 | 0.10 | 0.95 |
| revelation      | 0.50 | 0.20 | 1.00 |

All values stay inside the clamp by construction. The table lives in
`src/audio/tts/narrator_mood_map.py` as a module-level constant.

**Gating.** A single deterministic feature flag
`FeatureFlags.narrator_emotion_enabled` (default `False`, per TD-027's
hardcoded-flag model) gates whether the table applies. When off, narrator
uses the current `stability=0.65, style=0.05, speed=1.0` settings. When on,
narrator voice settings are derived from the chunk's `story_mood`.

**Scope of modulation.** Only the narrator voice settings are affected.
Character dialogue is untouched. Emotion labels (the existing per-beat
`emotion` field) are untouched — they continue to drive character voice.
Narrator beats no longer carry a per-beat emotion; the mood-driven settings
replace that channel for the narrator only.

## Acceptance Criteria

1. `src/config/feature_flags.py` gains one field:
   `narrator_emotion_enabled: bool = False`. Field is plain dataclass per
   TD-027 (no CLI / env / YAML surface).
2. `src/audio/tts/narrator_mood_map.py` defines `NARRATOR_MOOD_SETTINGS:
   dict[str, VoiceSettings]` covering every label in the US-034 whitelist.
3. A pure function `narrator_settings_for(mood: StoryMood) -> VoiceSettings`
   returns the mapped settings, asserting the result is within the narrator
   band. Unit-tested with 100% domain coverage.
4. `BeatSynthesizer` (or wherever narrator voice settings are resolved)
   consults `feature_flags.narrator_emotion_enabled`:
   - Off: uses current defaults (`stability=0.65, style=0.05, speed=1.0`).
   - On: resolves the chunk's `story_mood` and calls `narrator_settings_for`.
5. No changes to `section_parser.prompt`. The narrator-emotion feature is
   entirely deterministic code, consuming an already-emitted signal.
6. Character beats are unaffected — their voice settings continue to come
   from `voice_stability`, `voice_style`, `voice_speed` on the beat.
7. Existing voice-consistency evals pass without regression when the flag is
   off. When the flag is on, `make verify` produces audible narrator
   modulation on emotionally charged chunks.
8. `ruff check src/` and `mypy src/` pass.

## Out of Scope

- Detecting story mood (→ US-034).
- Music generation driven by story mood (→ US-012).
- Per-beat narrator emotion (explicitly rejected — narrator emotion comes
  from the story arc, not per-sentence LLM labels).
- Multiple narrator voices / narrator personas.
- Making the mapping table configurable from outside source. Edit the file.
- Learning or tuning the mapping table from audio feedback.

## Dependencies

- **US-034 — Story Mood Detection** (prerequisite). This spec cannot be
  implemented until `StoryMood` is available on the domain model.
- **TD-027 — Simplify Feature Flags** (soft prerequisite). This spec adds a
  flag to the simplified `FeatureFlags` class; ordering with TD-027 matters
  to avoid rework.

## Key Design Decisions

### Why deterministic table rather than LLM-chosen narrator settings?

- **Consistency.** A table guarantees identical mood → voice mapping across
  the whole book; the LLM would drift.
- **Tunability.** The audio engineer can adjust one number in one file; an
  LLM-driven mapping would require prompt engineering and re-parsing.
- **Cost.** Zero additional tokens. The signal already exists from US-034.

### Why the half-band clamp?

The user's explicit guidance: narrator should carry *some* emotion but not
act. The clamp is a hard invariant — even if the table were mis-edited, the
assertion in `narrator_settings_for` would fail loudly rather than let the
narrator drift into character-range expressiveness.

### Why default the flag to off?

The user has active books already generated with the neutral-narrator model.
Flipping narrator voice for those would invalidate cached audio. The flag
stays off until a new book is generated with the feature on from the start.

### Why not merge this into US-012?

Separate consumers of the same signal. Merging would triple US-012's scope
and couple shipping. The shared contract is the `StoryMood` signal in US-034,
which both specs depend on.
