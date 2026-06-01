"""AWS Bedrock AI provider implementation using Claude models."""
import json
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, ReadTimeoutError

from ..config import Config
from .ai_provider import AIProvider
from .token_tracker import TokenTracker

# Bedrock read timeout in seconds. Large chapters can take well over the
# default 60 seconds to process.
_BEDROCK_READ_TIMEOUT_SECONDS = 300


class AWSBedrockProvider(AIProvider):
    """AI provider using AWS Bedrock with Claude models.

    Token usage is tracked on every :meth:`generate` call via an injectable
    :class:`TokenTracker`. If no tracker is supplied, a private one is created
    and accessible via :attr:`token_tracker`.
    """

    def __init__(self, config: Config, *, token_tracker: Optional[TokenTracker] = None):
        self.config = config
        self.model_id = config.aws.bedrock_model_id
        self.token_tracker: TokenTracker = (
            token_tracker if token_tracker is not None else TokenTracker()
        )
        self._new_client()

    def _new_client(self) -> None:
        if self.config.aws.access_key_id and self.config.aws.secret_access_key:
            session = boto3.Session(
                aws_access_key_id=self.config.aws.access_key_id,
                aws_secret_access_key=self.config.aws.secret_access_key,
                aws_session_token=self.config.aws.session_token,
                region_name=self.config.aws.region,
            )
        else:
            session = boto3.Session(region_name=self.config.aws.region)

        boto_config = BotoConfig(read_timeout=_BEDROCK_READ_TIMEOUT_SECONDS)
        self.bedrock_runtime = session.client('bedrock-runtime', config=boto_config)

    def _build_request_body(self, prompt: str, max_tokens: int) -> dict:
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _invoke(self, request_body: dict) -> str:
        response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
        )
        response_body = json.loads(response['body'].read())
        usage = response_body.get("usage", {})
        self.token_tracker.record(
            model_id=self.model_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
        return response_body['content'][0]['text']

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        request_body = self._build_request_body(prompt, max_tokens)
        try:
            return self._invoke(request_body)
        except ReadTimeoutError as e:
            raise Exception(
                f"Bedrock request timed out after {_BEDROCK_READ_TIMEOUT_SECONDS} seconds. "
                f"Original error: {e}"
            )
        except ClientError as e:
            if "ExpiredTokenException" in str(e):
                self._new_client()
                try:
                    return self._invoke(request_body)
                except ClientError as retry_error:
                    raise Exception(f"AWS Bedrock API error: {retry_error}")
            raise Exception(f"AWS Bedrock API error: {e}")
