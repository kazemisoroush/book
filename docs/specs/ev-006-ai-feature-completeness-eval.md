# EV-006 — AI Feature Completeness Eval

## Goal

Create an eval that verifies the AI segmentation layer actually emits all supported segment types and features when given passages that should trigger them. This catches the class of bug where domain models and parser are updated but the AI prompt is not — the LLM never emits the new type and the feature silently does nothing.

---

## Problem

We added `SOUND_EFFECT` to `SegmentType`, updated the parser to handle it, added instructions and examples to the prompt — but forgot to add `"sound_effect"` to the prompt's type enumeration line. The LLM was told it could only emit 5 types, so it ignored the sound effect instructions entirely. The feature appeared to work (no errors) but produced zero sound effect segments.

This is a prompt-domain drift bug. The unit test we added (`test_prompt_type_enumeration_lists_every_ai_emittable_segment_type`) catches the mechanical drift. But we also need an end-to-end eval that confirms the AI **actually emits** all expected feature types when given appropriate input. The unit test catches "the prompt doesn't list the type"; the eval catches "the LLM doesn't emit the type even though it's listed."

The existing `score_ai_read` eval checks character detection and speaker attribution. The existing `score_sound_effect_detection` eval checks SFX detection in isolation. Neither checks the full set of AI-emitted features together.

---

## Concept

A single eval script runs golden-labeled passages through the real AI parser (AWS Bedrock) and checks that every expected feature appears in the output. Each passage is annotated with which features it should trigger.

**Features to check per passage:**
- Segment types emitted (NARRATION, DIALOGUE, SOUND_EFFECT, and future types)
- Emotion tags present on dialogue segments
- Scene detection (scene_id assigned)
- Voice settings populated (voice_stability, voice_style, voice_speed)
- Character detection and attribution (reuses golden passage annotations)
- New character descriptions (when a passage introduces a new character)

**One passage can check multiple features.** A Dracula passage with wolves howling checks both SOUND_EFFECT emission and emotion detection on the fearful dialogue.

---

## Acceptance criteria

1. New eval script `src/evals/score_ai_feature_completeness.py` that:
   - Runs golden passages through real `AISectionParser` + LLM
   - Scores recall (did the AI emit expected features?) and precision (did it avoid hallucinating?)
   - Accepts `--passage <name>` and `--verbose` flags
   - Uses 80% threshold (same as other AI evals)
   - Prints structured report with per-passage and aggregate results

2. New fixture file `src/evals/fixtures/golden_feature_passages.py` with:
   ```python
   @dataclass(frozen=True)
   class GoldenFeaturePassage:
       name: str
       text: str
       book_title: str
       book_author: str
       # Expected segment types the AI MUST emit (recall)
       expected_segment_types: list[str]  # e.g. ["dialogue", "narration", "sound_effect"]
       # Minimum counts per type
       min_segment_counts: dict[str, int]  # e.g. {"dialogue": 2, "sound_effect": 1}
       # Expected emotion tags (at least one segment should have this emotion or similar)
       expected_emotions: list[str]  # e.g. ["fear", "whisper"]
       # Whether scene detection should fire
       expect_scene: bool
       # Whether the passage should trigger NO sound effects (precision test)
       expect_no_sound_effects: bool = False
   ```

3. At least 3 golden passages:
   - **feature_rich**: A passage with dialogue, narration, sound effects, and emotion (e.g., Dracula wolf howling scene). Tests that all features fire together.
   - **emotion_shifts**: A passage with strong emotional changes mid-dialogue (e.g., Frankenstein's horror). Tests emotion detection.
   - **quiet_narration**: A passage with pure narration, no dialogue or sounds (e.g., Pride & Prejudice exposition). Precision test — should NOT emit sound effects or hallucinate dialogue.

4. Recall checks per passage:
   - Each expected segment type appears at least `min_segment_counts` times
   - At least one segment has an emotion matching each `expected_emotions` entry (fuzzy match)
   - Scene is detected when `expect_scene=True`

5. Precision checks per passage:
   - No SOUND_EFFECT segments when `expect_no_sound_effects=True`
   - All SOUND_EFFECT segments have `character_id=None`
   - All dialogue segments have a non-null `character_id`

6. Module docstring includes purpose, cost estimate ($0.50-$1.50), and usage

7. All existing tests continue to pass

---

## Out of scope

- Checking TTS output (this eval is AI layer only, not audio)
- Checking specific wording of AI output (non-deterministic)
- Voice design quality (separate eval in EV-005)
- Background music or ambient audio (those are TTS-layer features, not AI-emitted)
- Automated scoring of emotion accuracy beyond presence check
- CI integration (too expensive for every push)

---

## Key design decisions

### One eval for all AI features, not one per feature

The existing `score_sound_effect_detection` checks SFX in isolation. This eval checks all features together — closer to reality. A passage that triggers sound effects, emotions, and scenes simultaneously is more realistic than isolated tests and catches interactions (e.g., the AI drops sound effects when the passage is emotionally complex).

### Golden passages from real books

Same convention as existing evals. Real Gutenberg text, not synthetic. The passages are chosen to naturally trigger specific features.

### 80% threshold

Non-deterministic LLM output. Same threshold as other AI evals. The AI might miss one emotion or one sound effect on a given run — that's acceptable. Consistently missing an entire feature type (0% recall) is not.

### Fuzzy emotion matching

Emotions are free-form tags. "fear" might be emitted as "fearful", "afraid", "terrified", or "uneasy". The scorer does substring matching on emotion values, same approach as the sound effect label matching.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/evals/score_ai_feature_completeness.py` | **New** — eval scorer |
| `src/evals/fixtures/golden_feature_passages.py` | **New** — golden passages with feature annotations |

---

## Relationship to other specs

- **score_ai_read**: Existing eval for character detection — this eval reuses the pattern but checks more features
- **score_sound_effect_detection**: Existing eval for SFX — this eval subsumes its recall checks in a broader context
- **EV-005 (Granular TTS Evals)**: Tests TTS provider in isolation — complementary, not overlapping
- **US-031 (E2E Listening Eval)**: Tests full pipeline with audio output — this eval is cheaper (AI only, no TTS)

---

## Implementation notes

- Follow the `score_sound_effect_detection.py` pattern exactly: argparse CLI, golden passages, per-passage scoring, aggregate report
- Reuse `AISectionParser` + `AWSBedrockProvider` + `PromptBuilder` (same stack as existing AI evals)
- Fuzzy matching for emotions: check if expected emotion substring appears in any segment's emotion field
- Scene check: verify at least one segment has a non-null `scene_id` when `expect_scene=True`
- Cost: ~$0.10-0.30 per passage (3 passages = $0.30-$1.00 per run)
