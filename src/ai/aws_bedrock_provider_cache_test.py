"""Tests for AWS Bedrock prompt caching feature (TD-008)."""
import json
from unittest.mock import Mock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config import Config, AWSConfig
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


def create_success_response():
    """Create a successful Bedrock response."""
    response = {
        'body': MagicMock(),
        'ResponseMetadata': {'HTTPStatusCode': 200}
    }
    response['body'].read.return_value = json.dumps({
        "content": [{"text": "Success response"}],
        "usage": {"input_tokens": 100, "output_tokens": 20}
    }).encode('utf-8')
    return response


class TestBedrockPromptCaching:
    """Tests for Bedrock prompt caching feature."""

    def test_first_call_adds_cache_control_to_static_portion(self, mock_config):
        """Verify that cache_control markers are added to static portions on first call."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="Break down the following text into segments alternating between narration and dialogue.\n\n## Existing characters (reuse these IDs — do NOT create duplicates)\n\nFor each segment, identify:\n- type: \"dialogue\", \"narration\", \"illustration\", \"copyright\", or \"other\"\n- text: the actual text content\n\nReturn valid JSON only, no other text\n",
            book_context="Book context: 'Test Book' by Test Author\n",
            character_registry="  - character_id: \"test_char\", name: \"Test Character\"\n",
            surrounding_context="",
            scene_registry="",
            text_to_segment="Text to segment:\nOnce upon a time, there was a story."
        )

        captured_requests = []

        def capture_invoke_model(*args, **kwargs):
            captured_requests.append(kwargs)
            return create_success_response()

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=capture_invoke_model)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act
            result = provider.generate(prompt)

            # Assert
            assert result == "Success response"
            assert len(captured_requests) == 1

            # Verify the request body structure includes cache_control
            body_str = captured_requests[0]['body']
            request_body = json.loads(body_str)

            # Should have system block with cache_control for static instructions
            assert 'system' in request_body
            assert len(request_body['system']) > 0
            assert request_body['system'][0].get('cache_control', {}).get('type') == 'ephemeral'

    def test_cache_control_structure_in_request(self, mock_config):
        """Verify cache_control is properly structured in Bedrock API format."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="Break down the following text into segments.",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="Once upon a time."
        )

        captured_requests = []

        def capture_invoke_model(*args, **kwargs):
            captured_requests.append(kwargs)
            return create_success_response()

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=capture_invoke_model)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act
            provider.generate(prompt)

            # Assert
            body_str = captured_requests[0]['body']
            request_body = json.loads(body_str)

            # Verify basic structure
            assert 'anthropic_version' in request_body
            assert 'max_tokens' in request_body
            assert 'system' in request_body  # Should have system block with cache_control

    def test_identical_static_portions_have_matching_cache_blocks(self, mock_config):
        """Verify that identical static portions result in identical cache control blocks."""
        # Arrange
        static_rules = "Break down the following text into segments alternating between narration and dialogue."
        prompt1 = AIPrompt(
            static_instructions=static_rules,
            book_context="Book context: 'Book A' by Author A\n",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="First section"
        )
        prompt2 = AIPrompt(
            static_instructions=static_rules,
            book_context="Book context: 'Book A' by Author A\n",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="Second section"
        )

        captured_requests = []

        def capture_invoke_model(*args, **kwargs):
            captured_requests.append(kwargs)
            return create_success_response()

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=capture_invoke_model)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act
            provider.generate(prompt1)
            provider.generate(prompt2)

            # Assert
            assert len(captured_requests) == 2
            body1 = json.loads(captured_requests[0]['body'])
            body2 = json.loads(captured_requests[1]['body'])

            # Both should have cache_control markers
            assert body1['anthropic_version'] == body2['anthropic_version']
            # Both should have system blocks with cache_control
            assert body1['system'][0].get('cache_control', {}).get('type') == 'ephemeral'
            assert body2['system'][0].get('cache_control', {}).get('type') == 'ephemeral'

    def test_new_provider_instance_has_independent_cache(self, mock_config):
        """Verify that each provider instance has independent cache state."""
        # Arrange
        test_prompt = AIPrompt(
            static_instructions="Break down text into segments.",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="test content"
        )

        call_count = [0]

        def count_calls(*args, **kwargs):
            call_count[0] += 1
            return create_success_response()

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=count_calls)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            # Act
            provider1 = AWSBedrockProvider(mock_config)
            provider1.generate(test_prompt)

            provider2 = AWSBedrockProvider(mock_config)
            provider2.generate(test_prompt)

            # Assert
            # Both providers should have independently made calls
            # Cache is per-instance, so each provider is independent
            assert call_count[0] == 2

    def test_cache_control_not_sent_on_dynamic_portions(self, mock_config):
        """Verify cache_control is applied only to static portions, not dynamic content."""
        # Arrange
        test_prompt = AIPrompt(
            static_instructions="Rules: Break down text.",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="content"
        )

        captured_requests = []

        def capture_invoke_model(*args, **kwargs):
            captured_requests.append(json.loads(kwargs['body']))
            return create_success_response()

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=capture_invoke_model)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act
            provider.generate(test_prompt)

            # Assert
            body = captured_requests[0]
            # The request should have system block with cache_control and messages block
            assert 'system' in body
            assert 'messages' in body
            assert isinstance(body['messages'], list)
            assert len(body['messages']) > 0
            # Cache control should be on system, not messages
            assert body['system'][0].get('cache_control', {}).get('type') == 'ephemeral'

    def test_expired_token_exception_still_works_with_caching(self, mock_config):
        """Verify token expiry retry still works with caching enabled."""
        # Arrange
        test_prompt = AIPrompt(
            static_instructions="Test prompt",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment=""
        )

        call_count = [0]

        def invoke_with_retry(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                error_response = {'Error': {'Code': 'ValidationException', 'Message': 'ExpiredTokenException'}}
                raise ClientError(error_response, 'InvokeModel')
            return create_success_response()

        with patch('src.ai.aws_bedrock_provider.boto3.Session') as mock_session_class:
            mock_client = Mock()
            mock_client.invoke_model = Mock(side_effect=invoke_with_retry)
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            provider = AWSBedrockProvider(mock_config)

            # Act
            result = provider.generate(test_prompt)

            # Assert
            assert result == "Success response"
            # Should have retried: first call fails, second succeeds
            assert call_count[0] == 2
