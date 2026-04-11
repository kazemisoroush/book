# US-031 — End-to-End All-Features Listening Eval

## Goal

Create a single human-evaluated listening test that exercises every audio feature in the pipeline on a short, carefully chosen passage from a Project Gutenberg book. This eval validates the full parse → AI → TTS → audio assembly flow by producing audible output that a human can evaluate for quality and correctness. It replaces the need for many separate partial integration tests with one comprehensive test that costs a few dollars and runs in under 10 minutes.

---

## Problem

Today we have no end-to-end validation of the full pipeline. Unit tests verify individual modules. `make verify` runs AI parsing and outputs JSON, but produces no audio. Manual testing is ad hoc and expensive.

We need a systematic way to:
- Verify all audio features work together in production
- Listen to the output after major changes
- Catch integration bugs that unit tests miss
- Do this without spending tens of dollars on API calls

The current "run a full chapter" approach is too expensive and slow for regular use. A targeted short passage is more practical.

---

## Concept

### The Ideal Passage

We need a passage (1-3 paragraphs, 150-250 words) that naturally contains:

1. **Narration** — baseline narrator voice
2. **Dialogue** — at least 2 characters speaking
3. **Emotion shifts** — at least one segment with emotion (e.g., whispers, laughs, sighs)
4. **Sound effect moment** — explicit text like "a knock at the door" or "she coughed" that should trigger cinematic SFX
5. **Scene/ambient change** — a transition between two acoustic environments (e.g., drawing room → outside) so ambient cross-fade can be heard
6. **Background music** — ideally a scene with emotional weight (sad, tense, romantic) that justifies background music
7. **Character voice design** — at least one character rich enough to get a bespoke voice via Voice Design API

This is a tall order. No single passage from Pride & Prejudice naturally has all of these. The spec allows for two approaches:

**Option A (preferred):** Find a single passage from a well-known book (Dracula, Frankenstein, The Adventures of Sherlock Holmes) that hits most criteria naturally.

**Option B (fallback):** Use a custom synthetic passage written to exercise all features. This must still be narrative prose (no "test test test" nonsense), just crafted to include the right moments.

### Example Candidates

**Dracula, Chapter 1** — Jonathan Harker's arrival at the castle:
- Narration: Harker's journal entries
- Dialogue: Conversation with coachman, Count Dracula
- Emotion: Fear, unease
- Sound effects: Howling wolves, carriage wheels, door creaking
- Scene change: Outside in mountain pass → inside castle entrance
- Music: Tense/mysterious mood
- Voice design: Count Dracula (older male, Transylvanian accent, commanding)

**Frankenstein, Chapter 5** — The creature awakens:
- Narration: Victor's description
- Dialogue: Victor's exclamations
- Emotion: Horror, dread
- Sound effects: Creature's breathing, footsteps
- Scene change: Laboratory → streets outside
- Music: Dramatic/tense
- Voice design: Victor Frankenstein (young male, frantic, anxious)

**The Adventures of Sherlock Holmes, "A Scandal in Bohemia"** — Opening scene:
- Narration: Watson's description
- Dialogue: Holmes and Watson conversation
- Emotion: Dry wit, surprise
- Sound effects: Doorbell, footsteps, door knock
- Scene change: 221B Baker Street sitting room → hall
- Music: Mysterious
- Voice design: Sherlock Holmes (adult male, analytical, British accent)

---

## Acceptance criteria

1. New eval script `src/evals/run_e2e_listening_eval.py` that:
   - Takes a URL and chapter/section range as CLI arguments
   - Runs the full `TTSProjectGutenbergWorkflow` on the specified passage
   - Outputs a single MP3 file to a timestamped directory (e.g., `evals_output/e2e-2026-04-10-143022/chapter.mp3`)
   - Prints a structured checklist of what to listen for
   - Exits with status 0 (this is not an automated PASS/FAIL test)

2. CLI interface:
   ```bash
   python -m src.evals.run_e2e_listening_eval \
       --url <gutenberg_url> \
       --start-chapter N \
       --end-chapter N \
       --output-dir evals_output/
   ```

3. The eval uses **real API calls** for everything:
   - AWS Bedrock for AI parsing
   - ElevenLabs TTS for speech synthesis
   - ElevenLabs Voice Design for character voices
   - ElevenLabs Sound Effects for SFX and ambient
   - Suno AI for background music (if feature flag enabled)

4. The eval prints a human-readable checklist **after** audio generation:
   ```
   ══════════════════════════════════════════════════════════════
   E2E LISTENING EVAL — Generated audio ready for review
   ══════════════════════════════════════════════════════════════

   Output: evals_output/e2e-2026-04-10-143022/chapter.mp3
   Duration: 2:34

   Listen for the following features:

   [ ] NARRATION — Baseline narrator voice is clear and consistent
   [ ] DIALOGUE — At least 2 distinct character voices
   [ ] EMOTION — At least one segment with vocal emotion (e.g., whispers, laughs)
   [ ] SOUND EFFECTS — Diegetic SFX in silence gaps (e.g., knock, cough, footsteps)
   [ ] AMBIENT — Scene-appropriate background sound at correct volume
   [ ] SCENE TRANSITION — Ambient cross-fade when scene changes (if passage has scene change)
   [ ] BACKGROUND MUSIC — Music underscores emotional tone (if enabled and mood detected)
   [ ] VOICE DESIGN — At least one bespoke character voice matches description
   [ ] INTER-SEGMENT SILENCE — Natural pauses between segments
   [ ] NO AUDIO ARTIFACTS — No clicks, pops, or glitches in stitched audio

   Cost estimate: $2.50 - $5.00 (varies by passage length and features used)
   Runtime: ~5-8 minutes
   ```

5. A **golden passage** is documented in `src/evals/fixtures/golden_e2e_passage.py`:
   ```python
   @dataclass(frozen=True)
   class GoldenE2EPassage:
       """A passage for end-to-end listening evaluation."""
       name: str
       book_title: str
       gutenberg_url: str
       start_chapter: int
       end_chapter: int
       expected_features: list[str]  # e.g., ["dialogue", "sfx", "ambient"]
       notes: str  # What makes this passage a good test case
   ```

6. At least **one golden passage** is provided. Dracula Chapter 1 (first 3 sections) is the recommended default. The passage should be:
   - 150-250 words (short enough to run quickly)
   - From a well-known Project Gutenberg book (no copyright concerns)
   - Rich in audio features (hits at least 6 of the 7 criteria above)
   - Repeatable (same passage always produces comparable output)

7. The eval script has a `--passage` flag that loads a named passage from `golden_e2e_passage.py`:
   ```bash
   python -m src.evals.run_e2e_listening_eval --passage dracula_arrival
   ```

8. Module docstring includes:
   - Purpose: "Human-evaluated listening test for full pipeline"
   - Cost: "$2.50 - $5.00 per run"
   - Runtime: "~5-8 minutes"
   - Warning: "This eval makes real API calls and is NOT free"

9. All environment variables must be set or the eval exits with a clear error:
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - `ELEVENLABS_API_KEY`
   - `SUNO_API_KEY` (if background music is enabled)

10. The eval does **not** use pytest. It's a standalone script that prints output and writes an MP3. No PASS/FAIL logic. Human judgment is required.

---

## Out of scope

- Automated audio analysis (waveform comparison, silence detection, etc.)
- PASS/FAIL scoring (this is human-evaluated only)
- Multiple passages in one run (run the script multiple times for different passages)
- CI integration (too expensive; this is for manual use only)
- Comparison with previous runs (just listen to the output)
- Cost tracking (estimated cost printed, not actual billing)
- Text-to-feature mapping (the eval does not verify "knock at the door" produced a door knock sound — human listens and checks)

---

## Key design decisions

### Why a short passage instead of a full chapter?

Cost and time. A full chapter can take 30+ minutes and cost $20-50 depending on length and features. A 200-word passage runs in 5-8 minutes and costs $2-5. This makes the eval practical to run after major changes without breaking the bank.

### Why human evaluation instead of automated checks?

Audio quality cannot be mechanically verified. "Does this sound good?" requires a human ear. Automated checks (waveform matching, silence detection) are brittle and don't catch the problems we care about (unnatural pacing, wrong emotion, jarring ambient transitions).

### Why one passage instead of many?

One carefully chosen passage exercises all features. Multiple passages would multiply cost and time without adding much signal. If the single passage works, the pipeline works. If it doesn't, you have a concrete reproduction case to debug.

### Why Dracula instead of Pride & Prejudice?

Pride & Prejudice is great for dialogue and character detection (and is used in `score_ai_read.py`), but it lacks action, sound effects, and environmental variety. Dracula has all of these naturally. Frankenstein and Sherlock Holmes are also strong candidates.

### Why not a synthetic test passage?

Real literature is better for catching edge cases (unusual punctuation, complex sentence structure, narrative voice). A synthetic passage optimized for testing may miss problems that only appear in real prose. We prefer a passage from an actual book.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/evals/run_e2e_listening_eval.py` | **New module** — CLI script to run full pipeline on a short passage |
| `src/evals/fixtures/golden_e2e_passage.py` | **New module** — golden passage(s) for listening eval |

---

## Relationship to other specs

- **US-004 (TTS with ElevenLabs)**: Uses TTS provider
- **US-009 (Emotion-Aware TTS)**: Validates emotion features
- **US-011 (Ambient)**: Validates ambient sound mixing
- **US-012 (Background Music)**: Validates music mixing (if enabled)
- **US-014 (Voice Design)**: Validates bespoke character voices
- **US-016 (Inter-Segment Silence)**: Validates silence gaps
- **US-019 (TTS Context)**: Validates previous/next text context
- **US-020 (Scene/Acoustic Context)**: Validates scene detection and voice modifiers
- **US-023 (Cinematic SFX)**: Validates sound effects insertion
- **EV-005 (Granular ElevenLabs Evals)**: This is complementary — EV-005 tests TTS provider in isolation, US-031 tests the full pipeline end-to-end

---

## Implementation notes

### Suggested golden passage (Dracula, Chapter 1)

From **Dracula** by Bram Stoker (Project Gutenberg #345):
```
https://www.gutenberg.org/cache/epub/345/pg345.txt
```

Target the **opening scene** where Jonathan Harker arrives at the Borgo Pass and meets the mysterious coachman. This passage has:
- Narration: Harker's journal voice
- Dialogue: Coachman and passengers
- Emotion: Unease, fear
- Sound effects: Howling wolves, carriage wheels, horse hooves
- Scene change: Inside carriage → exposed at mountain pass
- Ambient: Mountain wind, distant wolves
- Music: Tense/mysterious mood

Approximate location: Chapter 1, first 250 words after the journal date "3 May. Bistritz."

### Cost breakdown

| Feature | API | Estimated Cost |
|---|---|---|
| AI parsing | AWS Bedrock | $0.10 - $0.30 |
| TTS synthesis (200 words, 3 voices) | ElevenLabs | $0.50 - $1.00 |
| Voice Design (1 bespoke voice) | ElevenLabs | $1.00 |
| Sound effects (2-3 SFX) | ElevenLabs | $0.30 - $0.60 |
| Ambient (1-2 scenes) | ElevenLabs | $0.20 - $0.40 |
| Background music (1 mood) | Suno AI | $0.40 - $0.70 |
| **Total** | | **$2.50 - $5.00** |

Actual cost varies by passage length, feature usage, and API pricing changes.

### Runtime breakdown

| Step | Estimated Time |
|---|---|
| Download + parse | 10-30 s |
| AI segmentation | 30-60 s |
| Voice Design | 60-120 s |
| TTS synthesis | 60-120 s |
| SFX generation | 10-30 s |
| Ambient generation | 10-30 s |
| Music generation | 30-60 s |
| Audio assembly (ffmpeg) | 5-10 s |
| **Total** | **5-8 minutes** |

### Testing the eval

To test the eval without the full passage, create a minimal test passage (1 sentence) and verify the script runs and produces output. Then test with the full golden passage.

### Checklist format

The checklist printed to stdout should be copy-pasteable into a notes file or issue comment. A human checks off items as they listen. Any unchecked items are bugs to investigate.
