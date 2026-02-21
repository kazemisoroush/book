"""AWS Bedrock AI provider implementation using Claude models."""
import json
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from .ai_provider import AIProvider, DialogueClassification
from ..config import Config


class AWSBedrockProvider(AIProvider):
    """AI provider using AWS Bedrock with Claude models."""

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

    def _invoke_model(self, prompt: str, max_tokens: int = 500) -> str:
        """Invoke the Claude model via Bedrock.

        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in response

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

    def classify_dialogue(self, paragraph: str, context: dict) -> DialogueClassification:
        """Classify whether quoted text is dialogue and identify the speaker.

        Args:
            paragraph: The paragraph containing quoted text
            context: Dictionary with context information

        Returns:
            DialogueClassification with is_dialogue flag and speaker name
        """
        # Build context string
        context_parts = []
        if context.get('recent_paragraphs'):
            context_parts.append("Previous context:")
            context_parts.extend(context['recent_paragraphs'][-3:])  # Last 3 paragraphs

        if context.get('known_characters'):
            context_parts.append(f"\nKnown characters: {', '.join(context['known_characters'])}")

        context_str = "\n".join(context_parts)

        prompt = f"""Analyze this paragraph from a novel and determine if the quoted text is character dialogue or just a quoted phrase/reference.

{context_str}

Current paragraph:
{paragraph}

Respond in JSON format:
{{
  "is_dialogue": true/false,
  "speaker": "character name" or null,
  "reasoning": "brief explanation"
}}

Guidelines:
- Dialogue requires speaker attribution (said X, replied Y, etc.) or clear conversational context
- Book titles, referenced phrases, and quotes without attribution are NOT dialogue
- If is_dialogue is true, provide the speaker's canonical name"""

        response = self._invoke_model(prompt)

        # Parse JSON response
        try:
            result = json.loads(response)
            return DialogueClassification(
                is_dialogue=result.get('is_dialogue', False),
                speaker=result.get('speaker'),
                confidence=0.9 if result.get('reasoning') else 0.7
            )
        except json.JSONDecodeError:
            # Fallback: if response contains "true" treat as dialogue
            is_dialogue = 'true' in response.lower()
            return DialogueClassification(is_dialogue=is_dialogue, confidence=0.5)

    def resolve_speaker(self, descriptor: str, context: dict) -> str:
        """Resolve a speaker descriptor to a canonical character name.

        Args:
            descriptor: The speaker descriptor (e.g., "his wife", "she", "lady")
            context: Dictionary with context information

        Returns:
            Canonical character name
        """
        # Build context string
        context_parts = []
        if context.get('paragraph'):
            context_parts.append(f"Current paragraph: {context['paragraph']}")

        if context.get('recent_paragraphs'):
            context_parts.append("\nPrevious paragraphs:")
            context_parts.extend(context['recent_paragraphs'][-3:])

        if context.get('known_characters'):
            context_parts.append(f"\nKnown characters: {', '.join(context['known_characters'])}")

        context_str = "\n".join(context_parts)

        prompt = f"""In this novel excerpt, determine the canonical character name for the descriptor "{descriptor}".

{context_str}

Respond with ONLY the canonical character name (e.g., "Mrs. Bennet", "Elizabeth Bennet").
If uncertain, respond with the descriptor as-is."""

        response = self._invoke_model(prompt, max_tokens=50)
        return response.strip().strip('"\'')

    def extract_characters(self, book_content: str) -> dict[str, list[str]]:
        """Extract all characters and their variations from a book.

        Args:
            book_content: The full text of the book (or sample)

        Returns:
            Dictionary mapping canonical names to list of variations
        """
        # For large books, use first ~10k characters as sample
        sample = book_content[:10000] if len(book_content) > 10000 else book_content

        prompt = f"""Analyze this excerpt from a novel and extract all character names and their variations.

{sample}

Respond in JSON format:
{{
  "characters": {{
    "Canonical Name": ["variation1", "variation2", "descriptor1"],
    ...
  }}
}}

Guidelines:
- Use full canonical names (e.g., "Mrs. Bennet", "Elizabeth Bennet")
- Include all variations: pronouns (she, he), descriptors (his wife, lady), nicknames (Lizzy)
- Group all variations under the same canonical name

Example:
{{
  "characters": {{
    "Mrs. Bennet": ["his wife", "his lady", "she", "lady"],
    "Elizabeth Bennet": ["Elizabeth", "Lizzy", "Eliza", "she"]
  }}
}}"""

        response = self._invoke_model(prompt, max_tokens=2000)

        try:
            result = json.loads(response)
            return result.get('characters', {})
        except json.JSONDecodeError:
            # Fallback: return empty dict
            return {}
