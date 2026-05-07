# AI Package

Contains abstractions for AI LLM interactions.

1. AIProvider: Abstract base for any LLM backend. Exposes a single generate(prompt, max_tokens) method that takes an AIPrompt and returns raw text. Keeps the rest of the codebase independent of any specific vendor so swapping Bedrock for Anthropic Direct, OpenAI, etc. is a one-class change. This class contains cost per token information.

2. AWSBedrockProvider: Concrete AIProvider that calls AWS Bedrock Claude. Accepts an optional TokenTracker so usage observation can be turned on without changing the call site.

3. TokenTracker: ONLY records per-call and cumulative token usage for every AIProvider invocation. Does NOT contain or track cost information that comes from AIProvider.

4. ModelPricingEntry: Encapsulates cost per token for each model. This is a dependency for AIProvider. Each provider should know how much it costs per token.

5. CallRecord: Immutable record of a single LLM invocation — model ID, input/output token counts. No cost estimation here.
