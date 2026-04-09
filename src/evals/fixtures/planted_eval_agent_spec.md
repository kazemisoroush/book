# Eval Spec: Emotion Detection Accuracy

**Goal**: Measure how accurately the AI segment parser detects emotions in dialogue.

## Context

The `AISectionParser` in `src/parsers/ai_section_parser.py` extracts emotion tags from dialogue segments. These tags are freeform lowercase auditory descriptions (e.g., "whispers", "laughs", "shouts angrily"). This eval measures whether the AI correctly identifies emotions when they are explicitly present in the text vs. hallucinating emotions that aren't there.

## Golden labels

Three passages from Project Gutenberg books, manually annotated with expected emotions:

1. **Pride and Prejudice, Chapter 1** - Mr. Bennet's dry sarcasm
   - Expected emotions: calm/neutral tone (no shouting or extreme emotions)
   - Passage: "Mr. Bennet replied that he had not." (after Mrs. Bennet's excitement)

2. **A Christmas Carol, Stave 1** - Scrooge's harsh rejection
   - Expected emotion: harsh/cold/dismissive tone
   - Passage: "Bah!" said Scrooge, "Humbug!"

3. **Alice in Wonderland, Chapter 1** - Alice's sleepy confusion
   - Expected emotion: drowsy/confused/neutral
   - Passage: Alice was beginning to get very tired of sitting by her sister on the bank...

## Acceptance criteria (eval checks)

**Recall (did the AI detect emotions when present?):**
1. Passage 2 (Scrooge) is tagged with some negative/harsh emotion indicator
2. Passage 3 (Alice) is tagged with some neutral/tired emotion indicator

**Precision (did the AI avoid hallucinating emotions?):**
1. Passage 1 (Mr. Bennet) does NOT have extreme emotions like "shouts" or "yells" (his tone is dry/calm)
2. None of the passages have hallucinated emotions that contradict the text (e.g., "laughs" when the character is clearly upset)

**Baseline threshold**: 80% (3/4 checks passing is acceptable for this AI feature)

## Files expected to be created

- `src/evals/fixtures/golden_emotion_detection.py` - The three annotated passages
- `src/evals/score_emotion_detection.py` - Scorer that runs AISectionParser on the passages and checks the results

## Out of scope

- Evaluating the full end-to-end workflow
- Testing voice assignment or TTS
- Testing scene detection or other AI features
