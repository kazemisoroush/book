# AI

Contains abstractions for AI LLM interactions.

## AIProvider

Abstract base for any LLM backend. Exposes a single generate(prompt, max_tokens) method that takes an AIPrompt and returns raw text. Keeps the rest of the codebase independent of any specific vendor so swapping Bedrock for Anthropic Direct, OpenAI, etc. is a one-class change.

### AnthropicProvider

### AWSBedrockProvider

Concrete AIProvider that calls AWS Bedrock Claude. Accepts an optional TokenTracker so usage observation can be turned on without changing the call site.

## TokenTracker

ONLY records per-call and cumulative token usage for every AIProvider invocation. No cost concept — cost is observable from the cloud provider's billing dashboard.

## CallRecord

Immutable record of a single LLM invocation — model ID, input/output token counts. No cost estimation here.
