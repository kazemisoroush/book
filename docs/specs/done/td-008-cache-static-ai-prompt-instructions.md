# TD-008: Use Bedrock Prompt Caching to Reduce LLM Token Costs

**Status**: Active
**Priority**: High
**Effort**: Medium
**Date Created**: 2026-04-06

## Goal

Reduce LLM (AWS Bedrock) token costs and latency by transparently using Bedrock's prompt caching feature. Cache the static portion of the AI segmentation prompt so it's only charged once, not on every section parse.

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

The **[STATIC RULES]** and **[Book context]** are identical across all 400+ sections. Caching these saves ~90% on ~80% of tokens sent to Bedrock.

**Estimated savings for a 400-section book:**
- Today: 400 sections × 2500 tokens/call = 1,000,000 tokens
- With caching: 1 × 2500 (first call) + 399 × 250 (90% discount) ≈ 102,500 effective tokens
- **Cost reduction: ~90%**

## Acceptance Criteria

1. **`AWSBedrockProvider` detects and caches static prompt portions automatically**
   - On first `generate()` call: sends full prompt with cache control markers on static sections
   - On subsequent `generate()` calls: if prompt prefix matches cached prefix, reuses cache (Bedrock does this automatically)
   - Caching is **transparent** — caller never knows about it

2. **Static prompt detection logic**
   - Extract "static instructions" from `AISectionParser._build_prompt()` — the block of rules, format examples, JSON structure (lines 348–477)
   - Split prompt into `[static_instructions]` + `[dynamic_context]` + `[text_to_segment]`
   - `AWSBedrockProvider` adds `cache_control: {"type": "ephemeral", "ttl": "5m"}` to the static block automatically
   - Dynamic blocks sent without cache control

3. **`AISectionParser` unchanged**
   - No modifications to public API or behavior
   - `_build_prompt()` returns same prompt as before
   - `AIProvider` interface stays clean (no `cache_control` parameter added)

4. **Cache lifecycle tied to `AWSBedrockProvider` instance**
   - Cache is active for the lifetime of the provider instance
   - When a new provider is created, cache resets
   - 5-minute Bedrock cache TTL handles automatic expiration

5. **All existing tests pass**
   - No changes to test assertions
   - Mocks continue to work as-is

## Out of Scope

- Tuning Bedrock cache TTL (use 5-minute default)
- Supporting other LLM providers' caching (only Bedrock for now)
- Caching LLM responses (only caching prompts)
- User-facing cache metrics or monitoring

## Implementation Notes

- Bedrock prompt caching requires minimum ~1024 tokens in cacheable section; our static instructions easily exceed this
- Cache control markers go in the message content structure, not as separate parameters
- Use `cache_control: {"type": "ephemeral"}` (no need to specify TTL; Bedrock uses default 5m)
- The static instructions must be **identical** between calls for cache hit; any character difference causes cache miss
- `AWSBedrockProvider.generate()` needs to:
  1. Extract static instructions from prompt
  2. Compare with previous call's static instructions
  3. Add cache control marker if static portion is same as before
  4. Send to Bedrock
