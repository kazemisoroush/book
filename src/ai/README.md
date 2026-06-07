# AI

Contains abstractions for AI LLM interactions.

## AIProvider

Abstract base for any LLM backend. Exposes a single `generate(prompt: str, max_tokens) -> str` method that takes a fully rendered prompt string and returns the model's response. Prompt assembly is the caller's responsibility (see `src.prompts.prompt_builder`). Keeps the rest of the codebase independent of any specific vendor so swapping Bedrock for Anthropic Direct, OpenAI, etc. is a one-class change.

### AnthropicProvider

Concrete AIProvider that calls the Anthropic API directly via the `anthropic` Python SDK.

### AWSBedrockProvider

Concrete AIProvider that calls AWS Bedrock Claude.

### ClaudeCodeProvider

Concrete AIProvider that drives `claude_agent_sdk.query()`, reusing the Claude Code CLI's OAuth session on the host. Calls bill against the signed-in claude.ai Pro/Max plan rather than an API key. Bridges the async SDK iterator to the synchronous `generate()` contract via `asyncio.run`. Best suited for smoke tests; full-book runs will hit Pro/Max quota throttling.
