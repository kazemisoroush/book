# Eval Spec: TextStats utility

**Goal**: Add a `TextStats` dataclass and a `compute_text_stats` function to
`src/domain/eval_orchestrator_target.py`.

## Acceptance criteria

1. `TextStats` is a frozen dataclass with fields: `word_count: int`,
   `sentence_count: int`, `avg_word_length: float`.
2. `compute_text_stats(text: str) -> TextStats` computes all three fields.
3. Sentences are split on `.`, `!`, `?` (ignoring empty splits).
4. Words are split on whitespace.
5. `avg_word_length` is the mean character count of all words, rounded to 1
   decimal place.  If the text has no words, `avg_word_length` is `0.0`.
6. An empty string returns `TextStats(word_count=0, sentence_count=0,
   avg_word_length=0.0)`.

## Files expected to change

- `src/domain/eval_orchestrator_target.py` — new module
- `src/domain/eval_orchestrator_target_test.py` — new test file

## Out of scope

- No CLI integration
- No logging
- No I/O
