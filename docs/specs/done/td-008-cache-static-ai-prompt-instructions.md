# TD-008: Use Structured AIPrompt Model with Cache-Friendly Methods

**Status**: Completed
**Priority**: High
**Effort**: Medium
**Date Created**: 2026-04-06

## Goal

Introduce a structured `AIPrompt` model that encapsulates prompt structure and provides cache-friendly builder methods. This enables any LLM provider to leverage prompt caching without extraction magic or abstraction leakage.

## Context

The `AISectionParser._build_prompt()` method generates prompts with this structure:

```
[STATIC RULES: 2000 words of instructions, examples, JSON format, etc.]
[Book context: title/author]
[Dynamic: Character registry]
[Dynamic: Surrounding context]
[Dynamic: Scene registry]
[Dynamic: Text to parse]
```

AWS Bedrock supports **prompt caching**: mark certain parts as cacheable, and subsequent requests with identical cached sections pay **90% less** for those tokens (~0.1x cost).

**Current problem:** The prompt is a single string with no structure. Providers must use fragile regex to extract static vs. dynamic portions.

**Solution:** Create an `AIPrompt` dataclass that:
- Stores the 6 prompt components as separate fields
- Provides `build_static_portion()` and `build_dynamic_portion()` methods
- Allows any provider to leverage caching without extraction logic

## Acceptance Criteria

1. **Create `AIPrompt` domain model in `src/domain/models.py`**
   - Frozen dataclass with 6 fields: `static_instructions`, `book_context`, `character_registry`, `surrounding_context`, `scene_registry`, `text_to_segment`
   - Method: `build_static_portion() -> str` - returns cacheable parts (static instructions + book context)
   - Method: `build_dynamic_portion() -> str` - returns per-section parts (registry + context + scene registry + text)
   - Method: `build_full_prompt() -> str` - returns complete concatenated prompt

2. **Update `AIProvider.generate()` signature**
   - Change from `generate(prompt: str, max_tokens: int)` to `generate(prompt: AIPrompt, max_tokens: int)`
   - Abstract interface now accepts structured prompts

3. **Update `AISectionParser._build_prompt()` to return `AIPrompt`**
   - Construct each field separately
   - Return `AIPrompt` instance instead of concatenated string
   - Update call site to pass `AIPrompt` to `ai_provider.generate()`

4. **Update `AWSBedrockProvider.generate()` to use cache-friendly methods**
   - Call `prompt.build_static_portion()` and `prompt.build_dynamic_portion()`
   - Remove `_extract_static_portion()` and `_extract_dynamic_portion()` helper methods
   - Apply cache control to static portion
   - No regex, no parsing, clean method calls

5. **Update all test mocks**
   - `MockAIProvider.generate(prompt: AIPrompt, ...)` signature
   - Tests can inspect `AIPrompt` fields directly
   - Update ~90 test call sites

6. **All tests pass**
   - 453 tests pass after refactoring
   - Lint and type checks clean

## Out of Scope

- Tuning Bedrock cache TTL (use 5-minute default)
- Prompt validation logic
- Multi-provider prompt adaptation strategies

## Implementation Notes

- `AIPrompt` is a frozen dataclass (immutable value object like `Scene`)
- The builder methods encapsulate formatting logic
- Any LLM provider can use these methods for caching, not just Bedrock
- Clean separation: domain model knows its structure, providers use it
- No extraction magic, no abstraction leakage
