"""Tests for AWS Bedrock AI provider."""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from .aws_bedrock_provider import AWSBedrockProvider
from .ai_provider import DialogueClassification
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

    def test_invoke_model_success(self, mock_config, mock_bedrock_client):
        """Test successful model invocation."""
        # Mock successful response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Test response'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider._invoke_model("Test prompt")

        assert result == "Test response"
        mock_bedrock_client.invoke_model.assert_called_once()

    def test_invoke_model_api_error(self, mock_config, mock_bedrock_client):
        """Test model invocation with API error."""
        # Mock API error
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid request'}},
            'InvokeModel'
        )

        provider = AWSBedrockProvider(mock_config)

        with pytest.raises(Exception, match="AWS Bedrock API error"):
            provider._invoke_model("Test prompt")

    def test_classify_dialogue_is_dialogue(self, mock_config, mock_bedrock_client):
        """Test dialogue classification for actual dialogue."""
        # Mock response indicating dialogue
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{
                'text': json.dumps({
                    'is_dialogue': True,
                    'speaker': 'Mrs. Bennet',
                    'reasoning': 'Has attribution "said his wife"'
                })
            }]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.classify_dialogue(
            '"My dear," said his wife.',
            {'known_characters': ['Mrs. Bennet']}
        )

        assert isinstance(result, DialogueClassification)
        assert result.is_dialogue is True
        assert result.speaker == 'Mrs. Bennet'
        assert result.confidence > 0.7

    def test_classify_dialogue_not_dialogue(self, mock_config, mock_bedrock_client):
        """Test dialogue classification for quoted phrase."""
        # Mock response indicating not dialogue
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{
                'text': json.dumps({
                    'is_dialogue': False,
                    'speaker': None,
                    'reasoning': 'Book title reference, no attribution'
                })
            }]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.classify_dialogue(
            'He mentioned "Pride and Prejudice" in his speech.',
            {}
        )

        assert isinstance(result, DialogueClassification)
        assert result.is_dialogue is False
        assert result.speaker is None

    def test_classify_dialogue_invalid_json_fallback(self, mock_config, mock_bedrock_client):
        """Test dialogue classification with invalid JSON response (fallback)."""
        # Mock invalid JSON response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'This is not valid JSON for our format'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.classify_dialogue('Some text', {})

        assert isinstance(result, DialogueClassification)
        assert result.confidence == 0.5  # Low confidence fallback

    def test_resolve_speaker(self, mock_config, mock_bedrock_client):
        """Test speaker resolution."""
        # Mock response with canonical name
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Mrs. Bennet'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.resolve_speaker(
            'his wife',
            {
                'paragraph': 'Mr. Bennet and his wife were talking.',
                'known_characters': ['Mrs. Bennet']
            }
        )

        assert result == 'Mrs. Bennet'

    def test_extract_characters(self, mock_config, mock_bedrock_client):
        """Test character extraction from book."""
        # Mock response with character mapping
        mock_response = {
            'body': Mock()
        }
        characters_data = {
            'characters': {
                'Mrs. Bennet': ['his wife', 'his lady', 'she'],
                'Elizabeth Bennet': ['Elizabeth', 'Lizzy', 'she']
            }
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': json.dumps(characters_data)}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.extract_characters('Sample book text...')

        assert isinstance(result, dict)
        assert 'Mrs. Bennet' in result
        assert 'his wife' in result['Mrs. Bennet']
        assert 'Elizabeth Bennet' in result
        assert 'Lizzy' in result['Elizabeth Bennet']

    def test_extract_characters_invalid_json_fallback(self, mock_config, mock_bedrock_client):
        """Test character extraction with invalid JSON (fallback)."""
        # Mock invalid JSON response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Invalid response'}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response

        provider = AWSBedrockProvider(mock_config)
        result = provider.extract_characters('Sample book text...')

        assert result == {}  # Empty dict fallback
