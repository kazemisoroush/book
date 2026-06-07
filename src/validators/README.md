# Validators

Deterministic checks that compare a `PromptInput` against a `PromptOutput` after the eval runs.

## Validator

Abstract base with one method `validate(prompt_input, prompt_output) -> ValidationResult`. Each concrete validator answers one question about the output. The eval runner runs a list of validators after writing the output and reports any whose result does not pass.

## ValidationResult

Frozen dataclass that carries a `deviation` float on a 0 to 1 scale. `0.0` means the actual output matches what the input implies; `1.0` means complete drift. The `passed` property is true when `deviation == 0.0`.

## TextValidator

Concatenates all input section texts, applies a list of `TextNormalizer` instances in order, does the same for all output beat texts, and scores the deviation as `1 - SequenceMatcher.ratio` between the two normalized strings. The constructor takes the normalizer list (order matters) and an optional `skip_types` set of section/beat types to exclude from the comparison.

## AssertionsValidator

Checks integer counts on the output against a sidecar `assertions.json` next to each eval case. Supported keys are `num_characters` and `num_beats`; missing keys are ignored so the file stays extensible. Per-assertion deviation is `abs(actual - expected) / max(actual, expected, 1)`; the result deviation is the mean across declared assertions.

## Normalizers subpackage

The text normalizers live in [normalizers/](normalizers/) and are composed by `TextValidator`.

### TextNormalizer

Abstract base with one method `normalize(text) -> text`. Each concrete normalizer does one thing and is immutable and stateless. Normalizers are composed by listing them in the order they should run.

### PunctuationNormalizer

Drops every character whose Unicode category starts with `P`. Removes ASCII punctuation, curly quotes, em-dashes, brackets, and braces. Whitespace is preserved.

### WhitespaceNormalizer

Replaces every run of whitespace with a single space and strips leading and trailing whitespace.

### LowercaseNormalizer

Lowercases every character, including non-ASCII letters.

## Adding a validator

Create a new class implementing `Validator`, write its test file alongside, and add it to the validator list passed into `_run_case` in the chapter_parser eval.

## Adding a normalizer

Create a new class implementing `TextNormalizer` inside [normalizers/](normalizers/), write its test file alongside, and add it to the normalizer list passed into `TextValidator`.
