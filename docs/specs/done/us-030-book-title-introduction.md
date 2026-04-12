# US-030 — Book Title and Introduction

## Goal

Add a spoken introduction at the start of every audiobook (before Chapter 1) that announces the book title and author, matching the professional audiobook convention of an opening title card. This provides essential context and creates a polished listening experience.

---

## Problem

Audiobooks produced by the current pipeline start directly with Chapter 1 narration. Listeners hear the story content immediately without any introduction of the book title or author. Professional audiobooks universally begin with a spoken introduction (e.g., "Pride and Prejudice, by Jane Austen") — the audiobook equivalent of a title page.

Without this introduction:
1. **Context is missing** — listeners don't hear the book title or author name
2. **Unprofessional feel** — audiobooks that skip the title intro feel incomplete or amateur
3. **Playlist confusion** — when listening to multiple books in sequence, there's no auditory marker of where one book ends and another begins

---

## Concept

Insert a synthetic "introduction segment" before Chapter 1 that speaks the book title and author name. This segment is generated via TTS using the narrator's voice.

**Audio structure per book:**
```
[Introduction: "Pride and Prejudice, by Jane Austen"]
[silence: 1.5 seconds]
[Chapter 1: regular narration begins...]
```

**Template format:**
```
"{title}, by {author}"
```

**Examples:**
- "Pride and Prejudice, by Jane Austen"
- "The Great Gatsby, by F. Scott Fitzgerald"
- "Moby-Dick, by Herman Melville"

The introduction is synthesized using the narrator's assigned voice (from `voice_assignment["narrator"]`) with no emotion tags, using the same TTS settings as standard narration.

---

## Acceptance criteria

1. `AudioOrchestrator` gains a new public method:
   ```python
   def synthesize_introduction(
       self,
       book: Book,
       voice_assignment: dict[str, str],
   ) -> Path:
       """Synthesize book title/author introduction.

       Output is written to output_dir/00-introduction/introduction.mp3.

       Args:
           book: The Book to synthesize an introduction for.
           voice_assignment: Mapping from character_id to voice_id.

       Returns:
           Path to the generated introduction.mp3 file.

       Raises:
           ValueError: If narrator voice_id not found in voice_assignment.
       """
   ```

2. The introduction text template is:
   ```python
   "{title}, by {author}"
   ```
   Where `title` and `author` are extracted from `book.metadata.title` and `book.metadata.author`.

3. Introduction segment is synthesized using:
   - Voice: `voice_assignment["narrator"]` (the narrator's assigned voice)
   - Emotion: `None` (no emotion tag)
   - No previous_text/next_text context (standalone utterance)
   - Standard TTS parameters (no voice modifiers)

4. Introduction audio is written to: `{output_dir}/00-introduction/introduction.mp3`
   - The `00-` prefix ensures it sorts before chapter folders (e.g., `01-Chapter-One`)
   - Directory is created if it doesn't exist

5. `TTSProjectGutenbergWorkflow.run()` is updated:
   - After voice assignment (Step 3), before synthesizing chapters (Step 4):
     - Call `audio_orchestrator.synthesize_introduction(book, voice_assignment)`
     - Log: `"tts_workflow_introduction_synthesized"` with `intro_path`
   - Introduction synthesis happens exactly once per book (not per chapter)

6. Introduction synthesis failures are **non-blocking**:
   - If `synthesize_introduction()` raises an exception, log it as a warning and continue to Chapter 1
   - The audiobook still produces successfully without the introduction

7. All existing tests continue to pass

8. New unit tests cover:
   - `AudioOrchestrator.synthesize_introduction()` produces correct text (`"{title}, by {author}"`)
   - Introduction uses narrator voice from `voice_assignment`
   - Introduction writes to correct path (`00-introduction/introduction.mp3`)
   - Introduction synthesis failure is logged but doesn't stop workflow
   - `TTSProjectGutenbergWorkflow` calls `synthesize_introduction()` before Chapter 1

---

## Out of scope

- Configurable introduction templates (hard-coded format is sufficient)
- Multi-narrator support (always uses `voice_assignment["narrator"]`)
- Introduction duration limits or speech rate adjustments (use default TTS settings)
- Custom introduction text (user-provided introduction content)
- Introduction for individual chapters (this is a book-level feature only)
- Stitching introduction into Chapter 1 audio (introduction is a separate file)
- Feature flag to disable introduction (always enabled)
- Localization/internationalization of template format (English-only)

---

## Key design decisions

### Why separate file instead of prepending to Chapter 1?

Separation of concerns: Chapter 1's audio remains pure chapter content. The introduction is book metadata, not narrative content. Keeping them separate:
- Allows skipping the introduction on re-listen
- Simplifies chapter-based playback controls
- Matches the structure of professional audiobooks (title card is a separate track)

### Why use narrator voice instead of a dedicated "announcer" voice?

Consistency: The narrator is the primary voice of the audiobook. Using a different voice for the title would be jarring. Professional audiobooks universally use the narrator's voice for title announcements.

### Why hard-code the template instead of making it configurable?

The "{title}, by {author}" format is a universal convention. No reasonable alternative exists. Hard-coding reduces complexity and removes an unnecessary configuration point. If a different format is needed in the future, it can be added as a new feature.

### Why non-blocking failure?

The introduction is enhancement, not core content. If TTS fails on the title card but succeeds on chapter content, the book is still usable. Logging the failure as a warning allows debugging without blocking book production.

### Why `00-introduction/` directory name?

The `00-` prefix ensures it sorts before chapter folders in filesystem listings and playlist views. This matches the natural listening order: introduction first, then chapters. The directory name is descriptive and unambiguous.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/audio/audio_orchestrator.py` | Add `synthesize_introduction()` method |
| `src/workflows/tts_project_gutenberg_workflow.py` | Call `synthesize_introduction()` before synthesizing chapters |

---

## Relationship to other specs

- **US-004 (TTS with ElevenLabs)**: Introduction uses same TTS synthesis path as regular narration
- **US-016 (Inter-Segment Silence)**: 1.5-second silence follows introduction (standard speaker-change gap)
- No direct dependencies on other specs

---

## Implementation notes

- Follow TDD: write tests for introduction text generation, synthesis call, and workflow integration before implementation
- Reuse existing `SegmentSynthesizer` for TTS synthesis (no need to duplicate synthesis logic)
- Introduction text sanitization: apply same `sanitize_segment_text()` logic used for regular segments
- Type annotations on all public methods
- Structured logging (`structlog.get_logger(__name__)`)
- No mocks beyond the TTS provider (at most 1 mock per test)
- Directory creation: use `Path.mkdir(parents=True, exist_ok=True)` pattern
