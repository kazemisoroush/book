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
        from botocore.exceptions import ClientError  # type: ignore[import-untyped]

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


class TestAWSBedrockProviderTokenTracking:
    """Tests for token tracking integration in AWSBedrockProvider."""

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

    @pytest.fixture
    def bedrock_response_with_usage(self):
        """Realistic Bedrock response body that includes a usage field."""
        body = {
            'content': [{'text': 'Hello from the model'}],
            'usage': {'input_tokens': 42, 'output_tokens': 17},
        }
        mock_resp = {'body': Mock()}
        mock_resp['body'].read.return_value = json.dumps(body).encode()
        return mock_resp

    def test_injected_tracker_records_tokens_from_response(
        self, mock_config, mock_bedrock_client, bedrock_response_with_usage
    ) -> None:
        """When a tracker is injected, generate() records the usage tokens from the response."""
        from src.ai.token_tracker import TokenTracker

        mock_bedrock_client.invoke_model.return_value = bedrock_response_with_usage
        tracker = TokenTracker()
        provider = AWSBedrockProvider(mock_config, token_tracker=tracker)

        provider.generate("Test prompt")

        assert tracker.call_count == 1
        assert tracker.cumulative_input_tokens == 42
        assert tracker.cumulative_output_tokens == 17

    def test_provider_creates_default_tracker_when_none_given(
        self, mock_config, mock_bedrock_client, bedrock_response_with_usage
    ) -> None:
        """When no tracker is passed, the provider creates its own and it records correctly."""
        from src.ai.token_tracker import TokenTracker

        mock_bedrock_client.invoke_model.return_value = bedrock_response_with_usage
        provider = AWSBedrockProvider(mock_config)

        provider.generate("Test prompt")

        assert isinstance(provider.token_tracker, TokenTracker)
        assert provider.token_tracker.call_count == 1

    def test_tracker_accumulates_across_multiple_generate_calls(
        self, mock_config, mock_bedrock_client
    ) -> None:
        """Two generate() calls accumulate tokens in the same injected tracker."""
        from src.ai.token_tracker import TokenTracker

        def make_response(input_tok: int, output_tok: int) -> dict:
            body = {
                'content': [{'text': 'reply'}],
                'usage': {'input_tokens': input_tok, 'output_tokens': output_tok},
            }
            resp = {'body': Mock()}
            resp['body'].read.return_value = json.dumps(body).encode()
            return resp

        mock_bedrock_client.invoke_model.side_effect = [
            make_response(100, 40),
            make_response(200, 60),
        ]
        tracker = TokenTracker()
        provider = AWSBedrockProvider(mock_config, token_tracker=tracker)

        provider.generate("First call")
        provider.generate("Second call")

        assert tracker.cumulative_input_tokens == 300
        assert tracker.cumulative_output_tokens == 100
        assert tracker.call_count == 2

    def test_generate_still_returns_text_when_usage_missing(
        self, mock_config, mock_bedrock_client
    ) -> None:
        """If the response has no 'usage' field, generate() still returns the text gracefully."""
        from src.ai.token_tracker import TokenTracker

        body = {'content': [{'text': 'response without usage'}]}
        mock_resp = {'body': Mock()}
        mock_resp['body'].read.return_value = json.dumps(body).encode()
        mock_bedrock_client.invoke_model.return_value = mock_resp

        tracker = TokenTracker()
        provider = AWSBedrockProvider(mock_config, token_tracker=tracker)

        result = provider.generate("prompt")

        assert result == 'response without usage'
        # Tracker should still record a call (with zero tokens as fallback)
        assert tracker.call_count == 1
