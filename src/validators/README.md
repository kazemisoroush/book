# Validators

Deterministic checks that compare a `PromptInput` against a `PromptOutput`. They run in two places: after each eval case, and inside `AIWorkflow` as a per-chapter gate that fails the workflow on any non-zero deviation.

## Validator

Abstract base with one method `validate(prompt_input, prompt_output) -> ValidationResult`. Each concrete validator answers one question about the output. The eval runner runs a list of validators after writing the output and reports any whose result does not pass.

## ValidationResult

Frozen dataclass that is a pure measurement: a `deviation` float on a 0 to 1 scale and an optional `detail` string. `0.0` deviation means the actual output matches what the input implies; `1.0` means complete drift. A validator uses `detail` to name what it found, for example which text was dropped. The result does not decide pass or fail; the metric does.

## Validator pass threshold

`Validator` owns the pass line. Its constructor takes a `threshold` with a sensible default, and `passed(result)` returns true when `result.deviation <= threshold`, so each metric declares what counts as passing while the result stays a plain measurement. The default threshold is `0.0`, a strict exact-match gate. `TextValidator` and `SectionCoverageValidator` default to `0.0`, while a count metric could accept a small tolerance.

## TextValidator

Concatenates all input section texts, applies a list of `TextNormalizer` instances in order, does the same for all output beat texts, and scores the deviation as `1 - SequenceMatcher.ratio` between the two normalized strings. The constructor takes the normalizer list (order matters) and an optional `skip_types` set of section/beat types to exclude from the comparison.

## SectionCoverageValidator

Metric that catches content the parse silently dropped. It normalizes the input sections and the output beats the same way `TextValidator` does, then reads the `SequenceMatcher` opcodes and flags every contiguous run of input text, at least `min_drop_chars` long, that the output lost. A run is lost when it is a delete, or a replace whose net loss (input length minus output length) is at least `min_drop_chars`, so a dropped sentence fails while an abbreviation expansion or a same-length word swap does not. The `detail` previews the dropped spans, up to the first `_MAX_REPORTED` and truncated to `_PREVIEW` characters each, so a failure points at the lost text. This is one metric in a family: more red-gate metrics can be added as further validators, and all text-comparing metrics share `TextComparingValidator` for the normalize and trim work.

## ValidationGateError

Exception raised by `AIWorkflow` when a chapter fails one or more validators. Carries the `book_id`, the `chapter_number`, and a `failures` list of validator name, deviation, and detail triples. Raised before the chapter is saved, so the repository never caches a failing chapter.

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
