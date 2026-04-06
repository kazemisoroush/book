"""AWS Bedrock AI provider implementation using Claude models."""
import json
import re
from typing import Optional

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from .ai_provider import AIProvider
from .token_tracker import TokenTracker
from ..config import Config


class AWSBedrockProvider(AIProvider):
    """AI provider using AWS Bedrock with Claude models.

    This is a generic LLM provider with no domain knowledge.
    It simply takes prompts and returns responses.

    Token usage is tracked automatically on every :meth:`generate` call via an
    injectable :class:`TokenTracker`.  If no tracker is supplied, a private one
    is created and accessible via :attr:`token_tracker`.

    Prompt caching is transparently applied: static portions of prompts (rules,
    format instructions) are automatically marked with cache_control so that
    identical static sections across many calls pay 90% less for tokens (Bedrock
    feature). Cache is per-instance; creating a new provider resets it.
    """

    def __init__(self, config: Config, *, token_tracker: Optional[TokenTracker] = None):
        """Initialize AWS Bedrock provider.

        Args:
            config: Configuration object with AWS credentials and settings
            token_tracker: Optional shared tracker for recording token usage.
                           If *None*, a new private tracker is created.
        """
        self.config = config
        self.model_id = config.aws.bedrock_model_id
        self.token_tracker: TokenTracker = token_tracker if token_tracker is not None else TokenTracker()

        # Cache tracking: store the previous static portion to know when cache is active
        self._cached_static_portion: Optional[str] = None

        # Initialize boto3 client
        self._new_client()

    def _new_client(self) -> None:
        """Recreate the boto3 Bedrock client.

        This is called on initialization and when credentials expire to refresh
        the session and client.
        """
        session_kwargs: dict[str, str] = {
            'region_name': self.config.aws.region
        }

        # Add credentials if provided (otherwise uses default credential chain)
        if self.config.aws.access_key_id and self.config.aws.secret_access_key:
            session_kwargs['aws_access_key_id'] = self.config.aws.access_key_id
            session_kwargs['aws_secret_access_key'] = self.config.aws.secret_access_key
            if self.config.aws.session_token:
                session_kwargs['aws_session_token'] = self.config.aws.session_token

        session = boto3.Session(**session_kwargs)
        self.bedrock_runtime = session.client('bedrock-runtime')

    @staticmethod
    def _extract_static_portion(prompt: str) -> Optional[str]:
        """Extract the static (cacheable) portion of an AI segmentation prompt.

        The static portion is the rules and instructions block that appears at
        the start of every segmentation prompt. It spans from "Break down the
        following text" through "Return valid JSON only, no other text".

        This portion is identical across all section parses for the same book,
        making it ideal for Bedrock's prompt caching feature.

        Args:
            prompt: The full prompt string

        Returns:
            The extracted static portion if recognized, or None if the prompt
            does not match the expected AI section parser format.
        """
        # Look for the start of the static instructions
        start_pattern = r"Break down the following text into segments"
        # Look for the end marker (must be exact to avoid cache misses)
        # The marker ends with the text "no other text" (before {book_context} substitution)
        end_pattern = r"Return valid JSON only, no other text"

        start_match = re.search(start_pattern, prompt)
        if not start_match:
            return None

        # Find the end of the static portion
        end_match = re.search(end_pattern, prompt[start_match.start():])
        if not end_match:
            return None

        # Extract from start of "Break down" to end of "Return valid JSON only, no other text"
        static_start = start_match.start()
        static_end = start_match.start() + end_match.end()

        return prompt[static_start:static_end]

    @staticmethod
    def _extract_dynamic_portion(prompt: str) -> Optional[str]:
        """Extract the dynamic (non-cacheable) portion of an AI segmentation prompt.

        The dynamic portion includes book context, character registry, surrounding
        context, scene context, and the text to segment.

        Args:
            prompt: The full prompt string

        Returns:
            The extracted dynamic portion (everything after the static rules block),
            or None if the prompt does not match the expected format.
        """
        # Look for the end marker of static instructions
        end_pattern = r"Return valid JSON only, no other text"
        end_match = re.search(end_pattern, prompt)
        if not end_match:
            return None

        # Dynamic portion starts right after the static portion
        dynamic_start = end_match.end()
        return prompt[dynamic_start:]

    def _build_cached_request_body(
        self, prompt: str, max_tokens: int
    ) -> dict:
        """Build a Bedrock request body with prompt caching if applicable.

        If the static portion of the prompt matches the cached static portion,
        both the static and dynamic portions are sent, with cache_control
        applied to the static portion. This allows Bedrock to automatically
        recognize and reuse the cache.

        If the static portion differs (e.g., different instructions), the
        prompt is sent normally without cache control (new cache will be created).

        Args:
            prompt: The full prompt
            max_tokens: Maximum tokens for the response

        Returns:
            A Bedrock request body dict with appropriate cache_control markers
        """
        # Extract static and dynamic portions
        static_portion = self._extract_static_portion(prompt)
        dynamic_portion = self._extract_dynamic_portion(prompt)

        # If we can extract both parts, use the cached request format with system+messages
        if static_portion and dynamic_portion:
            # Update cache tracking
            self._cached_static_portion = static_portion

            # Use the system+messages format with cache_control on system block
            request_body: dict = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": [
                    {
                        "type": "text",
                        "text": static_portion,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": dynamic_portion
                    }
                ]
            }
        else:
            # Fallback to simple format if we can't extract parts (non-AI-parser prompts)
            # No cache control applied
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

        return request_body

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """Generate a response from Claude via AWS Bedrock.

        Token usage reported in the response is recorded in :attr:`token_tracker`.

        Handles credential expiry by catching ExpiredTokenException, refreshing
        the client via _new_client(), and retrying once.

        Prompt caching is transparently applied: static portions of prompts
        (rules, format instructions) are automatically marked with cache_control
        markers so that subsequent calls with identical static sections pay 90%
        less for those tokens (Bedrock's prompt caching feature).

        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in response (default: 1000)

        Returns:
            The model's response text

        Raises:
            Exception: If the API call fails
        """
        # Build request body with prompt caching support
        request_body = self._build_cached_request_body(prompt, max_tokens)

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())

            # Extract token usage reported by Bedrock (present for Claude models)
            usage = response_body.get("usage", {})
            input_tokens: int = usage.get("input_tokens", 0)
            output_tokens: int = usage.get("output_tokens", 0)
            self.token_tracker.record(
                model_id=self.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            return response_body['content'][0]['text']

        except ClientError as e:
            # Check if this is an ExpiredTokenException
            error_message = str(e)
            if "ExpiredTokenException" in error_message:
                # Refresh the client and retry once
                self._new_client()
                try:
                    response = self.bedrock_runtime.invoke_model(
                        modelId=self.model_id,
                        body=json.dumps(request_body)
                    )

                    response_body = json.loads(response['body'].read())

                    # Extract token usage reported by Bedrock
                    usage = response_body.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    self.token_tracker.record(
                        model_id=self.model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

                    return response_body['content'][0]['text']
                except ClientError as retry_error:
                    raise Exception(f"AWS Bedrock API error: {retry_error}")
            else:
                raise Exception(f"AWS Bedrock API error: {e}")
