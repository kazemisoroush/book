# US-029 — Chapter Announcer

## Goal

Insert a spoken chapter announcement (e.g., "Chapter 1: The Beginning") at the start of each chapter's audio, providing listeners with clear chapter markers similar to professional audiobooks.

---

## Problem

The current TTS workflow synthesizes chapter beats and stitches them into a single audio file per chapter, but there is no audible marker indicating which chapter is playing. Listeners who pause mid-book or skip between chapters have no audio cue to orient themselves. Professional audiobooks consistently include chapter announcements narrated by a dedicated voice (often the narrator) to help listeners track their position in the book.

---

## Concept

The **AI beatation layer** emits a new `CHAPTER_ANNOUNCEMENT` beat as the first beat of each chapter. The AI decides the wording — it is not a deterministic template. The beat uses the narrator's `character_id` and carries no emotion, scene, or voice modifiers.

The **TTS layer** treats it like any other narratable beat — it reads the text as-is. The only special handling is that the pause **after** a `CHAPTER_ANNOUNCEMENT` is a dedicated constant (`SILENCE_AFTER_ANNOUNCEMENT_MS`), not derived from speaker-boundary logic.

**Example flow for Pride & Prejudice, Chapter 1:**
```
[CHAPTER_ANNOUNCEMENT: "Chapter One. It is a truth universally acknowledged..."]
[silence: 500ms — SILENCE_AFTER_ANNOUNCEMENT_MS, constant]
[NARRATION: "It is a truth universally acknowledged..."]
[silence: 150ms — same-speaker, constant]
[DIALOGUE: "My dear Mr. Bennet," said his lady...]
...
```

All pause durations are constants — 150ms (same-speaker), 400ms (speaker-change), 500ms (after announcement). None are variable or random.

---

## Acceptance criteria

1. `BeatType` gains a new member: `CHAPTER_ANNOUNCEMENT = "chapter_announcement"`

2. The `Beat` model adds `is_chapter_announcement` helper (mirrors `is_dialogue`, `is_narration`). `is_narratable` returns `True` for `CHAPTER_ANNOUNCEMENT` beats so the TTS reads them aloud.

3. The AI beatation layer emits a `CHAPTER_ANNOUNCEMENT` beat as the **first** beat of each chapter:
   - `character_id = "narrator"`
   - `emotion = None`, `scene_id = None`, no voice modifiers
   - Text is AI-generated (non-deterministic) — typically `"Chapter {N}. {Title}."` but the AI has creative freedom
   - When the chapter has no meaningful title (e.g., just "Chapter 1"), the announcement is shorter

4. The TTS layer synthesizes the `CHAPTER_ANNOUNCEMENT` beat like any other narratable beat — no special TTS logic beyond what applies to narration

5. Stitching: the pause **after** a `CHAPTER_ANNOUNCEMENT` beat is `SILENCE_AFTER_ANNOUNCEMENT_MS = 500` (a constant, same pattern as `SILENCE_SAME_SPEAKER_MS = 150` and `SILENCE_SPEAKER_CHANGE_MS = 400`). This overrides the normal speaker-boundary pause calculation when the previous beat is a chapter announcement.

6. Feature flag `chapter_announcer_enabled: bool = True` is added to `FeatureFlags` to allow disabling the feature

7. When `chapter_announcer_enabled=False`, the AI layer does not emit the `CHAPTER_ANNOUNCEMENT` beat — behavior is identical to today

8. New unit tests cover:
   - `CHAPTER_ANNOUNCEMENT` is a valid `BeatType` and is narratable
   - AI layer emits announcement as first beat with correct character_id and no emotion/scene
   - AI layer omits announcement when feature flag is disabled
   - TTS synthesizes announcement text without special handling
   - Stitching inserts 500ms constant pause after announcement beat
   - All existing tests continue to pass

---

## Out of scope

- Custom announcement voice (separate from narrator)
- Configurable silence duration after announcement
- Multiple announcement styles (formal vs. casual)
- Announcement volume adjustment (relative to narration)
- Announcement at chapter end (e.g., "End of Chapter 1")
- Book title announcement at the start of Chapter 1

---

## Key design decisions

### AI layer owns the announcement text

The announcement is a creative decision — the AI picks the wording. This keeps the TTS layer dumb (it just reads text) and keeps content decisions in the AI layer where they belong. The text is non-deterministic, like all other AI-generated beat content.

### New beat type, not a special flag

A first-class `CHAPTER_ANNOUNCEMENT` beat type is cleaner than a boolean flag on `Beat`. It follows the same pattern as `SOUND_EFFECT` — a distinct beat kind with its own semantics. The TTS and stitching layers can pattern-match on it.

### Constant pause after announcement

All pause durations in the system are constants per boundary type:
- 150ms — same speaker
- 400ms — speaker change  
- 500ms — after chapter announcement (new)

The 500ms value gives listeners a moment to register the chapter transition. It is not configurable (out of scope).

### Use narrator voice for consistency

The narrator is the primary storytelling voice. Using `character_id="narrator"` for the announcement reuses existing voice assignment — no new voice needed.

### Feature flag for opt-out

The flag gates at the AI layer (don't emit the beat). The TTS and stitching layers don't need to check the flag — if the beat isn't there, nothing happens.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `CHAPTER_ANNOUNCEMENT` to `BeatType`; add `is_chapter_announcement` helper; update `is_narratable` |
| `src/domain/models_test.py` | Tests for new beat type |
| `src/config/feature_flags.py` | Add `chapter_announcer_enabled: bool = True` |
| `src/ai/beater.py` (or equivalent) | Emit `CHAPTER_ANNOUNCEMENT` as first beat per chapter |
| `src/ai/beater_test.py` | Tests for announcement emission |
| `src/audio/audio_orchestrator.py` | Add `SILENCE_AFTER_ANNOUNCEMENT_MS = 500`; update `_build_concat_entries` to use it when previous beat is `CHAPTER_ANNOUNCEMENT` |
| `src/audio/audio_orchestrator_test.py` | Tests for announcement pause in stitching |

---

## Relationship to other specs

- **US-016 (Inter-Beat Silence)**: The 500ms silence after announcement reuses the silence generation mechanism, adds a new constant
- **US-019 (TTS Context)**: Announcement bypasses context resolution (no `previous_text`/`next_text`)
- **US-020 (Scenes)**: Announcement ignores scene context and voice modifiers
- **US-009 (Emotion-Aware TTS)**: Announcement is synthesized with no emotion tag
- **US-023 (Sound Effects)**: Follows the same pattern — new beat type with distinct semantics

---

## Implementation notes

- Follow TDD: write tests for beat type, AI emission, and stitching pause before implementation
- The AI prompt for beatation needs updating to emit `CHAPTER_ANNOUNCEMENT` as the first beat
- No mocks beyond the TTS provider call for synthesis (at most 1 mock per test)
- Structured logging: log announcement generation with chapter number
- Type annotations on all public functions
