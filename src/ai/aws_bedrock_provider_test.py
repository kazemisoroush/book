"""Tests for AWS Bedrock AI provider."""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from .aws_bedrock_provider import AWSBedrockProvider
from ..config import Config, AWSConfig


class TestAWSBedrockProvider:
    """Tests for AWSBedrockProvider."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return Config(
            aws=AWSConfig(
                region='us-east-1',
                bedrock_model_id='us.anthropic.claude-sonnet-4-20250514-v1:0',
                access_key_id='test-key',
                secret_access_key='test-secret'
            )
        )

    @pytest.fixture
    def mock_bedrock_client(self):
        """Create a mock Bedrock runtime client."""
        with patch('boto3.Session') as mock_session:
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client
            yield mock_client

    def test_init_with_credentials(self, mock_config, mock_bedrock_client):
        """Test initialization with explicit credentials."""
        provider = AWSBedrockProvider(mock_config)

        assert provider.config == mock_config
        assert provider.model_id == 'us.anthropic.claude-sonnet-4-20250514-v1:0'

    def test_init_without_credentials(self, mock_bedrock_client):
        """Test initialization without explicit credentials (uses default chain)."""
        config = Config(
            aws=AWSConfig(
                region='us-west-2',
                bedrock_model_id='test-model'
            )
        )

        provider = AWSBedrockProvider(config)

        assert provider.config == config

    def test_generate_success(self, mock_config, mock_bedrock_client):
        """Test successful text generation."""
        # Mock successful response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'This is the AI response'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.generate("What is 2+2?")

        assert result == "This is the AI response"
        mock_bedrock_client.invoke_model.assert_called_once()

        # Verify the request format
        call_args = mock_bedrock_client.invoke_model.call_args
        assert call_args[1]['modelId'] == 'us.anthropic.claude-sonnet-4-20250514-v1:0'

        request_body = json.loads(call_args[1]['body'])
        assert request_body['messages'][0]['content'] == "What is 2+2?"
        assert request_body['max_tokens'] == 1000  # default

    def test_generate_with_custom_max_tokens(self, mock_config, mock_bedrock_client):
        """Test generation with custom max_tokens."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Short response'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.generate("Test prompt", max_tokens=100)

        assert result == "Short response"

        # Verify max_tokens was passed correctly
        call_args = mock_bedrock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]['body'])
        assert request_body['max_tokens'] == 100

    def test_generate_api_error(self, mock_config, mock_bedrock_client):
        """Test generation with API error."""
        # Mock API error
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid request'}},
            'InvokeModel'
        )

        provider = AWSBedrockProvider(mock_config)

        with pytest.raises(Exception, match="AWS Bedrock API error"):
            provider.generate("Test prompt")

    def test_generate_long_prompt(self, mock_config, mock_bedrock_client):
        """Test generation with a long prompt (like character registry)."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': '{"speaker": "Mrs. Bennet", "registry": {}}'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)

        long_prompt = """
        Current character registry:
        {"Mrs. Bennet": {"aliases": ["Mrs. Bennet"], "context": "..."}}

        New dialogue: "Hello," said his wife
        Previous paragraph: Mr. Bennet was reading.

        Task: Identify the speaker and return updated registry.
        """

        result = provider.generate(long_prompt, max_tokens=2000)

        assert '{"speaker": "Mrs. Bennet"' in result

        # Verify request was made correctly
        call_args = mock_bedrock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]['body'])
        assert 'Current character registry' in request_body['messages'][0]['content']
        assert request_body['max_tokens'] == 2000
