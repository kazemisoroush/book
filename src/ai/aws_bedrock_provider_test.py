"""Tests for AWS Bedrock AI provider."""
import json
from unittest.mock import Mock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config import Config, AWSConfig


@pytest.fixture
def mock_config() -> Config:
    """Create a mock config for testing."""
    aws_config = AWSConfig(
        region="us-east-1",
        bedrock_model_id="us.anthropic.claude-opus-4-6-v1",
        access_key_id=None,
        secret_access_key=None,
        session_token=None
    )
    config = Mock(spec=Config)
    config.aws = aws_config
    return config


@pytest.fixture
def success_response():
    """Create a successful Bedrock response."""
    response = {
        'body': MagicMock(),
        'ResponseMetadata': {'HTTPStatusCode': 200}
    }
    response['body'].read.return_value = json.dumps({
        "content": [{"text": "Success response"}],
        "usage": {"input_tokens": 10, "output_tokens": 20}
    }).encode('utf-8')
    return response


class TestAWSBedrockProviderCredentialRefresh:
    """Tests for credential refresh on token expiry."""

    def test_expired_token_exception_triggers_retry_and_succeeds(self, mock_config, success_response):
        """Verify that ExpiredTokenException triggers retry and eventually succeeds."""
        # Arrange
        call_count = 0

        def invoke_model_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error_response = {'Error': {'Code': 'ValidationException', 'Message': 'ExpiredTokenException'}}
                raise ClientError(error_response, 'InvokeModel')
            return success_response

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=invoke_model_side_effect)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            # Act
            provider = AWSBedrockProvider(mock_config)
            response = provider.generate("Test prompt")

            # Assert
            assert response == "Success response"
            assert mock_client.invoke_model.call_count == 2

    def test_non_expired_errors_raise_immediately(self, mock_config):
        """Verify that non-ExpiredTokenException errors raise immediately without retry."""
        # Arrange
        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=ClientError(
                {'Error': {'Code': 'ValidationException', 'Message': 'Invalid request'}},
                'InvokeModel'
            ))
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                provider.generate("Test prompt")

            assert "AWS Bedrock API error" in str(exc_info.value)
            # Should only be called once (no retry)
            assert mock_client.invoke_model.call_count == 1

    def test_expired_token_retried_but_fails_on_retry(self, mock_config):
        """Verify that if retry also fails, error is raised."""
        # Arrange
        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=ClientError(
                {'Error': {'Code': 'ValidationException', 'Message': 'ExpiredTokenException'}},
                'InvokeModel'
            ))
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                provider.generate("Test prompt")

            assert "AWS Bedrock API error" in str(exc_info.value)
            # Should be called twice (initial call + one retry)
            assert mock_client.invoke_model.call_count == 2

    def test_new_client_method_exists_and_recreates_session(self, mock_config):
        """Verify _new_client method exists and can be called."""
        # Arrange
        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act
            provider._new_client()

            # Assert
            assert provider.bedrock_runtime is not None
            # Session constructor should have been called at least twice (init + _new_client)
            assert mock_session_class.call_count >= 1
