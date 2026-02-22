"""AWS Bedrock AI provider implementation using Claude models."""
import json
import boto3
from botocore.exceptions import ClientError

from .ai_provider import AIProvider
from ..config import Config


class AWSBedrockProvider(AIProvider):
    """AI provider using AWS Bedrock with Claude models.

    This is a generic LLM provider with no domain knowledge.
    It simply takes prompts and returns responses.
    """

    def __init__(self, config: Config):
        """Initialize AWS Bedrock provider.

        Args:
            config: Configuration object with AWS credentials and settings
        """
        self.config = config
        self.model_id = config.aws.bedrock_model_id

        # Initialize boto3 client
        session_kwargs = {
            'region_name': config.aws.region
        }

        # Add credentials if provided (otherwise uses default credential chain)
        if config.aws.access_key_id and config.aws.secret_access_key:
            session_kwargs['aws_access_key_id'] = config.aws.access_key_id
            session_kwargs['aws_secret_access_key'] = config.aws.secret_access_key
            if config.aws.session_token:
                session_kwargs['aws_session_token'] = config.aws.session_token

        session = boto3.Session(**session_kwargs)
        self.bedrock_runtime = session.client('bedrock-runtime')

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """Generate a response from Claude via AWS Bedrock.

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
            return response_body['content'][0]['text']

        except ClientError as e:
            raise Exception(f"AWS Bedrock API error: {e}")
