"""AWS Bedrock AI provider implementation using Claude models."""
import json

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, ReadTimeoutError

from ..config import Config
from .ai_provider import AIProvider

# Bedrock read timeout in seconds. Large chapters can take well over the
# default 60 seconds to process.
_BEDROCK_READ_TIMEOUT_SECONDS = 300


class AWSBedrockProvider(AIProvider):
    """AI provider using AWS Bedrock with Claude models."""

    def __init__(self, config: Config):
        self.config = config
        self.model_id = config.aws.bedrock_model_id
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
