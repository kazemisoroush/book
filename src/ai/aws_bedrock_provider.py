"""AWS Bedrock AI provider implementation using Claude models."""
import json
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

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """Generate a response from Claude via AWS Bedrock.

        Token usage reported in the response is recorded in :attr:`token_tracker`.

        Handles credential expiry by catching ExpiredTokenException, refreshing
        the client via _new_client(), and retrying once.

        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in response (default: 1000)

        Returns:
            The model's response text

        Raises:
            Exception: If the API call fails
        """
        # Bedrock Claude API format
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
