"""AWS Bedrock AI provider implementation using Claude models."""
import json
from typing import Optional

import boto3  # type: ignore[import-untyped]
from botocore.config import Config as BotoConfig  # type: ignore[import-untyped]
from botocore.exceptions import ClientError, ReadTimeoutError  # type: ignore[import-untyped]

from .ai_provider import AIProvider
from .token_tracker import TokenTracker
from ..config import Config
from ..domain.models import AIPrompt


# Bedrock read timeout in seconds. Large sections (e.g., multi-page letters)
# can take well over the default 60 seconds to process.
_BEDROCK_READ_TIMEOUT_SECONDS = 300


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

        # Configure increased read timeout for large section processing
        boto_config = BotoConfig(
            read_timeout=_BEDROCK_READ_TIMEOUT_SECONDS
        )

        self.bedrock_runtime = session.client('bedrock-runtime', config=boto_config)


    def _build_cached_request_body(
        self, prompt: AIPrompt, max_tokens: int
    ) -> dict:
        """Build a Bedrock request body with prompt caching via AIPrompt methods.

        Uses AIPrompt's build_static_portion() and build_dynamic_portion() methods
        to segment the prompt cleanly. The static portion is marked with cache_control
        so that subsequent calls with identical static sections pay 90% less for
        those tokens (Bedrock's prompt caching feature).

        Args:
            prompt: The structured AIPrompt object
            max_tokens: Maximum tokens for the response

        Returns:
            A Bedrock request body dict with cache_control on the static portion
        """
        static_portion = prompt.build_static_portion()
        dynamic_portion = prompt.build_dynamic_portion()

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

        return request_body

    def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str:
        """Generate a response from Claude via AWS Bedrock.

        Token usage reported in the response is recorded in :attr:`token_tracker`.

        Handles credential expiry by catching ExpiredTokenException, refreshing
        the client via _new_client(), and retrying once.

        Handles read timeouts by catching ReadTimeoutError and wrapping it in a
        descriptive exception. The boto3 client is configured with a 300-second
        read timeout to accommodate large sections.

        Prompt caching is transparently applied: the static portion of the prompt
        is marked with cache_control markers so that subsequent calls with identical
        static sections pay 90% less for those tokens (Bedrock's prompt caching feature).

        Args:
            prompt: The structured AIPrompt to send to the model
            max_tokens: Maximum tokens in response (default: 1000)

        Returns:
            The model's response text

        Raises:
            Exception: If the API call fails or times out
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

        except ReadTimeoutError as e:
            raise Exception(
                f"Bedrock request timed out after {_BEDROCK_READ_TIMEOUT_SECONDS} seconds. "
                f"This can occur when processing exceptionally large sections. "
                f"Original error: {e}"
            )

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
