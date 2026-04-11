# US-032 — Anthropic Direct AI Provider

## Goal

Add a second AI provider that calls the Anthropic Claude API directly via the
`anthropic` Python SDK, as an alternative to the existing `AWSBedrockProvider`
which routes through AWS Bedrock. This gives users without an AWS account a
simpler path to run the pipeline using only an Anthropic API key, and decouples
the project from AWS infrastructure for AI inference.

## Problem

Today the only AI provider is `AWSBedrockProvider`, which requires AWS
credentials, a Bedrock-enabled region, and an IAM setup. Users who already have
an Anthropic API key must still go through AWS. There is no way to select a
provider at runtime — the workflow factory hardcodes `AWSBedrockProvider`.

## Acceptance criteria

1. A new file `src/ai/anthropic_provider.py` exists containing a class
   `AnthropicProvider(AIProvider)` with the following public signature:
   ```python
   class AnthropicProvider(AIProvider):
       def __init__(
           self,
           config: Config,
           *,
           token_tracker: Optional[TokenTracker] = None,
       ) -> None: ...

       def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str: ...
   ```

2. `AnthropicProvider.generate()` calls the Anthropic Messages API using the
   `anthropic` Python SDK (i.e., `anthropic.Anthropic().messages.create()`),
   not boto3.

3. `AnthropicProvider` applies prompt caching: the static portion of the prompt
   (returned by `prompt.build_static_portion()`) is sent as a `system` block
   with `"cache_control": {"type": "ephemeral"}`, matching the structure used by
   `AWSBedrockProvider._build_cached_request_body()`.

4. `AnthropicProvider.generate()` calls `self.token_tracker.record()` with
   `model_id`, `input_tokens`, and `output_tokens` extracted from the SDK
   response's `usage` object after every successful call.

5. A new `AnthropicConfig` dataclass is added to `src/config/config.py`:
   ```python
   @dataclass
   class AnthropicConfig:
       api_key: Optional[str]
       model_id: str

       @classmethod
       def from_env(cls) -> 'AnthropicConfig': ...
   ```
   `api_key` is loaded from `ANTHROPIC_API_KEY` (default `None`).
   `model_id` is loaded from `ANTHROPIC_MODEL_ID` (default
   `"claude-opus-4-5-20251101"`).

6. `Config` gains a new field `anthropic: AnthropicConfig` populated by
   `AnthropicConfig.from_env()` inside `Config.from_env()`. No existing fields
   are removed or renamed.

7. `Config` gains a new field `ai_provider: str` loaded from the `AI_PROVIDER`
   env var (default `"bedrock"`). Valid values are `"bedrock"` and
   `"anthropic"`.

8. `Config.validate()` calls `sys.exit(1)` with a logged error when
   `ai_provider` is `"anthropic"` and `config.anthropic.api_key` is `None` or
   empty.

9. `Config.validate()` calls `sys.exit(1)` with a logged error when
   `ai_provider` is not one of `["bedrock", "anthropic"]`.

10. The factory method `AIProjectGutenbergWorkflow.create()` in
    `src/workflows/ai_project_gutenberg_workflow.py` selects the provider based
    on `config.ai_provider`: `"anthropic"` instantiates `AnthropicProvider`;
    anything else (default `"bedrock"`) instantiates `AWSBedrockProvider`. No
    other logic in `create()` changes.

11. A test file `src/ai/anthropic_provider_test.py` exists. It contains tests
    that:
    - Verify `generate()` returns the text content from a mocked SDK response.
    - Verify `token_tracker.record()` is called with the correct `model_id`,
      `input_tokens`, and `output_tokens` from the mocked response's `usage`.
    - Verify the system block sent to the SDK contains
      `"cache_control": {"type": "ephemeral"}` on the static portion.

12. `AnthropicProvider` is importable from `src/ai/anthropic_provider.py`
    without raising `ImportError` (i.e., `anthropic` is listed as a dependency
    in `pyproject.toml`).

13. All existing tests continue to pass (`pytest -v`).

14. `ruff check src/` and `mypy src/` report zero errors.

## Concept

The mapping from Bedrock request body to Anthropic SDK call is direct:

```
Bedrock                               Anthropic SDK
──────────────────────────────────    ────────────────────────────────────────
system[0].text = static_portion       system=[{"type": "text",
system[0].cache_control               "text": static_portion,
                                      "cache_control": {"type": "ephemeral"}}]
messages[0].role = "user"             messages=[{"role": "user",
messages[0].content = dynamic         "content": dynamic_portion}]
max_tokens                            max_tokens=max_tokens
response_body["usage"]                response.usage (sdk object)
response_body["content"][0]["text"]   response.content[0].text
```

The Anthropic SDK returns `response.usage.input_tokens` and
`response.usage.output_tokens` directly as integers, so no `dict.get()` is
needed.

## Key design decisions

- **No retry on API error.** `AWSBedrockProvider` retries on
  `ExpiredTokenException` because temporary credentials are common with AWS
  roles. Anthropic API keys do not expire mid-session; if the call fails, raise
  immediately. Retry logic can be added later as a separate TD spec if needed.
- **No new base class.** Both providers implement the existing `AIProvider`
  interface. The selection logic lives only in the workflow factory — no
  strategy pattern, registry, or factory class is introduced.
- **Config is extended, not refactored.** `AnthropicConfig` is added alongside
  `AWSConfig`; neither is renamed or restructured. The `ai_provider` field on
  `Config` is the single routing switch.
- **Token tracking reuses `TokenTracker` as-is.** `TokenTracker` already
  supports any `model_id` string and uses a substring-match pricing fallback for
  unknown models. No changes to `TokenTracker` are required.

## Files changed (expected)

| File | Change |
|------|--------|
| `src/ai/anthropic_provider.py` | New file — `AnthropicProvider` class |
| `src/ai/anthropic_provider_test.py` | New file — unit tests for `AnthropicProvider` |
| `src/config/config.py` | Add `AnthropicConfig` dataclass, `anthropic` field on `Config`, `ai_provider` field on `Config`, update `from_env()` and `validate()` |
| `src/workflows/ai_project_gutenberg_workflow.py` | Update `create()` to branch on `config.ai_provider` |
| `pyproject.toml` | Add `anthropic` to dependencies |

## Out of scope

- Pricing entries for Anthropic direct API model IDs in `token_tracker.py` (the
  existing substring-match fallback handles this; a dedicated pricing update is
  a separate TD).
- Streaming responses.
- Retry logic for `AnthropicProvider` on transient API errors.
- Any changes to `AWSBedrockProvider`.
- CLI argument (`--ai-provider`) — env var only for now.
- Eval harness or integration test against the live Anthropic API.
- Support for any AI provider other than `"bedrock"` and `"anthropic"`.
