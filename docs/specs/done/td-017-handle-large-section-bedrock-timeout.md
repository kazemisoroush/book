# TD-017 — Handle Large Section Bedrock Timeout

## Goal

Prevent AI parsing failures on exceptionally large book sections (such as
multi-page letters or monologues) that exceed the default boto3 read timeout
for AWS Bedrock `invoke_model` calls.

## Problem

Chapter 35 of *Pride and Prejudice* contains Darcy's letter — a single
section spanning several pages of continuous prose. When `AISectionParser`
sends this section to `AWSBedrockProvider.generate()`, the Bedrock
`invoke_model` call times out because:

1. **No explicit timeout is configured.** `AWSBedrockProvider._new_client()`
   creates the boto3 client with default settings. The default botocore read
   timeout is 60 seconds. A large section produces a large prompt (the section
   text itself plus the static instructions, character registry, context
   window, and scene registry). The LLM needs well over 60 seconds to process
   and generate the full segmented JSON response for a section of this size.

2. **There is no section size limit or splitting.** The parser sends the
   entire section text to the LLM in a single request regardless of length.
   `AISectionParser.parse()` passes `section.text` directly to
   `PromptBuilder.build_prompt()` with no size check.

3. **The retry logic does not help.** `AISectionParser` retries up to 3 times
   on empty or unparseable responses, but a boto3 timeout raises a
   `ClientError` (or `ReadTimeoutError`) which propagates as an unhandled
   exception — it is not caught by the retry loop.

The result is a hard failure that blocks processing of any book containing a
section longer than approximately 3,000–4,000 words.

## Concept

Two complementary changes address this:

### A. Increase the boto3 read timeout for Bedrock calls

Add a `botocore.config.Config` with an increased `read_timeout` to the
`bedrock-runtime` client in `AWSBedrockProvider._new_client()`. A value of
300 seconds (5 minutes) provides adequate headroom for the largest sections
found in Project Gutenberg novels without being so high that genuine network
failures hang the process.

This is a low-risk, high-impact fix: it eliminates the immediate timeout
without changing the parsing pipeline.

### B. (Future) Pre-split oversized sections before AI parsing

A pre-processing step could split sections exceeding a configurable word
threshold (e.g., 2,000 words) into smaller sub-sections at paragraph or
sentence boundaries before sending them to the LLM. This would reduce
per-call latency and token cost. However, splitting a continuous prose section
(like a letter with no paragraph breaks) is non-trivial — naive splitting
mid-paragraph risks breaking speaker attribution and emotional continuity.

This spec covers **approach A only**. Approach B is noted as future work and
explicitly out of scope.

## Acceptance criteria

1. `AWSBedrockProvider._new_client()` creates the `bedrock-runtime` client
   with a `botocore.config.Config` that sets `read_timeout` to 300 seconds.
   The `connect_timeout` remains at the botocore default (60 seconds).

2. The `read_timeout` value (300) is defined as a module-level constant
   `_BEDROCK_READ_TIMEOUT_SECONDS` in `src/ai/aws_bedrock_provider.py`, not
   buried inside the method body.

3. A unit test in `src/ai/aws_bedrock_provider_test.py` asserts that the
   boto3 client is constructed with the expected `read_timeout` configuration.
   This test must use at most one mock.

4. `AWSBedrockProvider.generate()` catches `ReadTimeoutError` from botocore
   (in addition to the existing `ClientError` handling) and wraps it in a
   descriptive `Exception` message that includes the timeout value and a hint
   about section size, so the user knows what happened.

5. A unit test asserts that when `invoke_model` raises `ReadTimeoutError`,
   `generate()` raises an `Exception` with a message containing both
   "timeout" and "300".

6. All existing tests continue to pass. `mypy src/` and `ruff check src/`
   produce no new errors.

## Files changed (expected)

| File | Change |
|---|---|
| `src/ai/aws_bedrock_provider.py` | Add `botocore.config.Config` import, define `_BEDROCK_READ_TIMEOUT_SECONDS = 300`, pass config to `session.client()`, catch `ReadTimeoutError` in `generate()` |
| `src/ai/aws_bedrock_provider_test.py` | Add tests for timeout configuration and `ReadTimeoutError` handling |

## Implementation notes

- The `botocore.config.Config` object is passed via the `config` kwarg of
  `session.client('bedrock-runtime', config=botocore_config)`.
- Import: `from botocore.config import Config as BotoConfig` (aliased to
  avoid collision with `src.config.Config`).
- Import: `from botocore.exceptions import ReadTimeoutError` (this is
  distinct from `ClientError`).
- The existing `ClientError` / `ExpiredTokenException` handling in
  `generate()` must remain unchanged.

## Out of scope

- Pre-splitting oversized sections before sending to the AI (approach B
  above). This is a separate, more complex change that requires its own spec
  once we have data on how often large sections occur across the corpus.
- Making the timeout configurable via environment variable or `AWSConfig`.
  A constant is sufficient until there is evidence that different deployments
  need different values.
- Streaming Bedrock responses (`invoke_model_with_response_stream`). This
  would eliminate the read timeout concern entirely but requires changes to
  the response parsing pipeline.
- Retry-on-timeout logic. The existing retry loop in `AISectionParser`
  handles parse failures, not transport failures. Adding transport-level
  retries is a separate concern.
