# Validators

Deterministic equivalence check between a `PromptInput` and a `PromptOutput`.

## Validator

Concatenates all input section texts, applies a list of `TextNormalizer` instances in order, does the same for all output beat texts, and returns `True` when the two normalized strings are equal. The constructor takes the normalizer list (order matters) and an optional `skip_types` set of section/beat types that should be excluded from the comparison.

## TextNormalizer

Abstract base with one method `normalize(text) -> text`. Each concrete normalizer does one thing and is immutable and stateless. Normalizers are composed by listing them in the order they should run.

## PunctuationNormalizer

Drops every character whose Unicode category starts with `P`. Removes ASCII punctuation, curly quotes, em-dashes, brackets, and braces. Whitespace is preserved.

## WhitespaceNormalizer

Replaces every run of whitespace with a single space and strips leading and trailing whitespace.

## LowercaseNormalizer

Lowercases every character, including non-ASCII letters.

## Adding a normalizer

Create a new class implementing `TextNormalizer`, write its test file alongside, and add it to the normalizer list passed into `Validator`.
