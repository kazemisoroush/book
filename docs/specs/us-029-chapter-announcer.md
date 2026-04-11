# US-029 — Chapter Announcer

## Goal

Insert a spoken chapter announcement (e.g., "Chapter 1: The Beginning") at the start of each chapter's audio, providing listeners with clear chapter markers similar to professional audiobooks.

---

## Problem

The current TTS workflow synthesizes chapter segments and stitches them into a single audio file per chapter, but there is no audible marker indicating which chapter is playing. Listeners who pause mid-book or skip between chapters have no audio cue to orient themselves. Professional audiobooks consistently include chapter announcements narrated by a dedicated voice (often the narrator) to help listeners track their position in the book.

---

## Concept

Before synthesizing the chapter's content segments, generate a brief audio announcement stating the chapter number and title. This announcement is prepended to the chapter audio during the stitching phase.

**Example flow for Pride & Prejudice, Chapter 1:**
```
[announcement: "Chapter 1. It is a truth universally acknowledged..."]
[silence: 500ms]
[first narration segment: "It is a truth universally acknowledged..."]
...
```

The announcement uses the narrator's assigned voice to maintain consistency with the book's narration voice.

---

## Acceptance criteria

1. `TTSOrchestrator.synthesize_chapter()` generates a chapter announcement before synthesizing content segments:
   - Text format: `"Chapter {number}. {title}."` (e.g., `"Chapter 1. The Beginning."`)
   - Voice: Uses the narrator's voice from `voice_assignment["narrator"]`
   - Output: Saved as `announcement.mp3` in the chapter directory

2. The announcement audio is prepended to the chapter's audio during stitching:
   - Order: `[announcement.mp3] + [silence_500ms.mp3] + [seg_0000.mp3] + ... + [seg_NNNN.mp3]`
   - A 500ms silence gap is inserted between the announcement and the first content segment

3. When `chapter.title` is empty or only contains the chapter number (e.g., "Chapter 1"), the announcement text simplifies to `"Chapter {number}."` (no title suffix)

4. The announcement is synthesized with neutral settings (no emotion, scene, or voice modifiers) regardless of the first segment's context

5. Feature flag `chapter_announcer_enabled: bool = True` is added to `FeatureFlags` to allow disabling the feature

6. When `chapter_announcer_enabled=False`, behavior is identical to today (no regression)

7. In debug mode (`debug=True`), `announcement.mp3` is kept in the chapter folder alongside segment files

8. In normal mode (`debug=False`), the announcement is synthesized to the temporary directory like other segments and cleaned up after stitching

9. New unit tests cover:
   - Announcement text formatting with title present
   - Announcement text formatting with title absent or redundant
   - Announcement is prepended to segment list during stitching
   - 500ms silence is inserted after announcement
   - Feature flag disable skips announcement generation
   - Narrator voice is used for announcement

10. All existing tests continue to pass

---

## Out of scope

- Custom announcement voice (separate from narrator)
- Configurable announcement text format (e.g., omitting title)
- Configurable silence duration after announcement
- Multiple announcement styles (formal vs. casual)
- Announcement volume adjustment (relative to narration)
- Announcement at chapter end (e.g., "End of Chapter 1")
- Book title announcement at the start of Chapter 1

---

## Key design decisions

### Use narrator voice for consistency

The narrator is the primary storytelling voice, so using it for chapter announcements maintains a consistent listening experience. This avoids introducing a new "announcer" character that would require voice assignment.

### Simple text format: "Chapter N. Title."

This format is concise, unambiguous, and matches common audiobook conventions. More elaborate formats (e.g., "You are now listening to Chapter 1: The Beginning") would feel intrusive and break immersion.

### Neutral TTS settings for announcement

Unlike story segments, announcements are meta-narrative and should not carry emotion, scene context, or voice modifiers. This keeps them distinct from the narrative flow and prevents awkward mismatches (e.g., an angry announcement).

### 500ms gap after announcement

This matches the `SILENCE_SPEAKER_CHANGE_MS` default (400ms) rounded up for a slightly longer pause, giving listeners a moment to register the chapter transition before content begins. Long enough to feel deliberate, short enough to avoid impatience.

### Feature flag for opt-out

While chapter announcements are a standard audiobook feature, some users may prefer a seamless listening experience without interruptions. The feature flag allows disabling at the orchestrator level without code changes.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/config/feature_flags.py` | Add `chapter_announcer_enabled: bool = True` field |
| `src/tts/tts_orchestrator.py` | Generate announcement audio; prepend to concat list |
| `src/tts/tts_orchestrator_test.py` | Tests for announcement generation and insertion |

---

## Relationship to other specs

- **US-016 (Inter-Segment Silence)**: The 500ms silence after announcement reuses the silence generation mechanism
- **US-019 (TTS Context)**: Announcement bypasses context resolution (no `previous_text`/`next_text`)
- **US-020 (Scenes)**: Announcement ignores scene context and voice modifiers
- **US-009 (Emotion-Aware TTS)**: Announcement is synthesized with no emotion tag

---

## Implementation notes

- Follow TDD: write tests for announcement text formatting, prepending, and feature flag before implementation
- Inject dependencies: announcement synthesis uses the existing `TTSProvider`, not a separate provider
- No mocks beyond the TTS provider call for synthesis (at most 1 mock per test)
- Structured logging: log announcement generation with chapter number and title
- Type annotations on all public functions
- The announcement text must be sanitized via `sanitize_segment_text()` to prevent TTS artifacts (consistent with segment handling)
