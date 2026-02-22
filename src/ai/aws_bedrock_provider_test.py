"""Tests for AWS Bedrock AI provider."""
import json
import pytest
from unittest.mock import Mock, patch
from src.config import AWSConfig
from .aws_bedrock_provider import AWSBedrockProvider


class TestAWSBedrockProvider:
    """Tests for AWSBedrockProvider."""

    @pytest.fixture
    def mock_bedrock_client(self):
        """Mock boto3 bedrock client."""
        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def mock_config(self):
        """Create a mock config with AWS settings."""
        config = Mock()
        config.aws = AWSConfig(
            region='us-east-1',
            bedrock_model_id='us.anthropic.claude-sonnet-4-20250514-v1:0'
        )
        return config

    def test_init_with_credentials(self, mock_bedrock_client):
        """Test initialization with explicit credentials."""
        aws_config = AWSConfig(
            region='eu-west-1',
            bedrock_model_id='another-model',
            access_key_id='test-key',
            secret_access_key='test-secret',
            session_token='test-token'
        )

        mock_config = Mock()
        mock_config.aws = aws_config

        provider = AWSBedrockProvider(mock_config)

        assert provider.config == mock_config
        assert provider.model_id == 'another-model'

    def test_init_without_credentials(self, mock_bedrock_client):
        """Test initialization without explicit credentials (uses default chain)."""
        aws_config = AWSConfig(
            region='us-west-2',
            bedrock_model_id='test-model'
        )

        mock_config = Mock()
        mock_config.aws = aws_config

        provider = AWSBedrockProvider(mock_config)

        assert provider.config == mock_config
        assert provider.model_id == 'test-model'

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
        result = provider.generate("Test prompt")

        assert result == 'This is the AI response'
        mock_bedrock_client.invoke_model.assert_called_once()

    def test_generate_with_custom_max_tokens(self, mock_config, mock_bedrock_client):
        """Test generation with custom max_tokens parameter."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Response text'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        provider.generate("Prompt", max_tokens=2000)

        # Check that max_tokens was passed in the request
        call_args = mock_bedrock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]['body'])
        assert request_body['max_tokens'] == 2000

    def test_generate_api_error(self, mock_config, mock_bedrock_client):
        """Test handling of API errors."""
        from botocore.exceptions import ClientError

        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid request'}},
            'invoke_model'
        )

        provider = AWSBedrockProvider(mock_config)

        with pytest.raises(Exception, match="AWS Bedrock API error"):
            provider.generate("Test prompt")

    def test_generate_long_prompt(self, mock_config, mock_bedrock_client):
        """Test handling of long prompts."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'AI response to long prompt'}]
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

        result = provider.generate(long_prompt, max_tokens=2500)

        assert result == 'AI response to long prompt'
        call_args = mock_bedrock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]['body'])
        assert request_body['max_tokens'] == 2500
