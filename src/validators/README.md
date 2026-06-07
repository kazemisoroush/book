# Validators

Deterministic checks that compare a `PromptInput` against a `PromptOutput` after the eval runs.

## Validator

Abstract base with one method `validate(prompt_input, prompt_output) -> bool`. Each concrete validator answers one question about the output. The eval runner runs a list of validators after writing the output and reports any that return `False`.

## TextValidator

Concatenates all input section texts, applies a list of `TextNormalizer` instances in order, does the same for all output beat texts, and returns `True` when the two normalized strings are equal. The constructor takes the normalizer list (order matters) and an optional `skip_types` set of section/beat types to exclude from the comparison.

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
