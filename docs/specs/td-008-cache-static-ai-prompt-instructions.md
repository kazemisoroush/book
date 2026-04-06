# TD-008: Use Bedrock Prompt Caching to Reduce LLM Token Costs

**Status**: Active
**Priority**: High
**Effort**: Medium
**Date Created**: 2026-04-06

## Goal

Reduce LLM (Bedrock) token costs and latency by leveraging AWS Bedrock's prompt caching feature. Cache the static portion of the AI segmentation prompt (~2.5KB of rules, format instructions, and examples) so it's only charged once, not on every section parse.

## Context

The `AISectionParser._build_prompt()` method sends a large, identical prompt structure to the LLM for every section. AWS Bedrock supports **prompt caching**: if you mark certain parts of the prompt as cacheable, the first request pays for those tokens normally, but subsequent requests with the same cached tokens pay at a **90% discount** (~0.1x cost).

The prompt structure is:
```
[STATIC RULES: 2000 words of instructions, examples, JSON format, etc.]
[Book context: title/author]
[Dynamic: Character registry]
[Dynamic: Surrounding context]
[Dynamic: Scene registry]
[Dynamic: Text to parse]
```

The **[STATIC RULES]** and **[Book context]** are identical across all 400+ sections. Caching these saves 90% on ~80% of tokens sent to the LLM.

**Estimated savings:** If we parse 400 sections and send ~2500 tokens per call:
- Today: 400 × 2500 = 1,000,000 tokens cost
- With caching: 1 × 2500 (first call) + 399 × 250 (90% discount) = ~102,500 effective tokens cost
- **Cost reduction: ~90%**

## Acceptance Criteria

1. **Update `AIProvider.generate()` signature** in `src/ai/ai_provider.py`
   - Add optional parameter `cache_control: Optional[dict[str, str]] = None`
   - When provided, pass cache control directives to the LLM API

2. **Update `AWSBedrockProvider.generate()`** to support cache control
   - Accept `cache_control` parameter
   - Pass it to Bedrock API via `system_prompt_cache_control` or equivalent Bedrock parameter
   - First call: Bedrock caches the prompt, charges full price
   - Subsequent calls: Bedrock uses cache, charges 90% less

3. **Update `AISectionParser._build_prompt()`** to mark static sections as cacheable
   - Split prompt into two parts:
     - `static_instructions`: Rules, examples, JSON format (cacheable)
     - `dynamic_context`: Registry, surrounding sections, scene registry, text to parse (not cacheable)
   - Return both; let the caller decide how to send them to the LLM

4. **Update `AISectionParser.parse()`** to use cache control on first section only
   - First section parse: pass `cache_control={"type": "ephemeral"}` to `ai_provider.generate()`
   - Subsequent sections: pass `cache_control=None` (implicitly uses cached version from first call)
   - Cache remains active for the lifetime of the `AISectionParser` instance

5. **Update `TTSProjectGutenbergWorkflow`** to reuse `AISectionParser` instance across all chapters
   - Currently: Each section gets a fresh `AISectionParser` (no caching benefit)
   - After fix: Single `AISectionParser` instance for entire book (caching works across all chapters)
   - Move `section_parser` initialization outside the chapter loop

6. **All existing tests pass**
   - Mocks can safely ignore `cache_control` parameter
   - No changes to test assertions or test data

## Out of Scope

- Tuning cache TTL (use Bedrock defaults)
- Switching LLM providers that don't support prompt caching
- Caching LLM responses themselves (only the prompt)

## Implementation Notes

- Bedrock prompt caching is documented at: https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
- Cache control should only apply to the static instructions block, not dynamic context
- Once a cache is created on the first call, all subsequent calls in that session automatically reuse it
- Cache is per-`AISectionParser` instance; creating a new parser resets the cache
- Ensure `AIProjectGutenbergWorkflow` creates a single `AISectionParser` and reuses it (don't create a new one per chapter)
