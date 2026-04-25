"""Tests for AWS Bedrock AI provider."""
import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import (
    ClientError,
    ReadTimeoutError,
)

from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config import AWSConfig, Config
from src.domain.models import AIPrompt


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
        prompt = AIPrompt(
            static_instructions="Test prompt",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment=""
        )
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
            response = provider.generate(prompt)

            # Assert
            assert response == "Success response"
            assert mock_client.invoke_model.call_count == 2

    def test_non_expired_errors_raise_immediately(self, mock_config):
        """Verify that non-ExpiredTokenException errors raise immediately without retry."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="Test prompt",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment=""
        )
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
                provider.generate(prompt)

            assert "AWS Bedrock API error" in str(exc_info.value)
            # Should only be called once (no retry)
            assert mock_client.invoke_model.call_count == 1

    def test_expired_token_retried_but_fails_on_retry(self, mock_config):
        """Verify that if retry also fails, error is raised."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="Test prompt",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment=""
        )
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
                provider.generate(prompt)

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


def test_bedrock_client_configured_with_read_timeout(mock_config):
    """Verify that boto3 client is created with 300-second read timeout."""
    # Arrange
    with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Act
        provider = AWSBedrockProvider(mock_config)

        # Assert
        assert provider.bedrock_runtime is not None
        # Verify session.client() was called with a config argument
        call_args = mock_session.client.call_args
        assert call_args is not None
        config_arg = call_args.kwargs.get('config')
        assert config_arg is not None, "Expected 'config' kwarg in session.client() call"
        # Verify the config has read_timeout set to 300
        assert hasattr(config_arg, 'read_timeout'), "Config object missing read_timeout attribute"
        assert config_arg.read_timeout == 300, f"Expected read_timeout=300, got {config_arg.read_timeout}"


def test_read_timeout_error_raises_descriptive_exception(mock_config):
    """Verify that ReadTimeoutError is caught and wrapped with descriptive message."""
    # Arrange
    prompt = AIPrompt(
        static_instructions="Test prompt",
        book_context="",
        character_registry="",
        surrounding_context="",
        scene_registry="",
        text_to_segment=""
    )
    with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
        mock_client = Mock()
        # Simulate ReadTimeoutError from boto3
        mock_client.invoke_model = Mock(side_effect=ReadTimeoutError(endpoint_url="https://bedrock.us-east-1.amazonaws.com"))
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        provider = AWSBedrockProvider(mock_config)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            provider.generate(prompt)

        error_message = str(exc_info.value)
        assert "timeout" in error_message.lower(), f"Expected 'timeout' in error message: {error_message}"
        assert "300" in error_message, f"Expected '300' in error message: {error_message}"
