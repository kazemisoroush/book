"""AWS-specific configuration for the audiobook generator."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AWSConfig:
    """AWS-specific configuration."""
    region: str
    bedrock_model_id: str
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'AWSConfig':
        """Load AWS configuration from environment variables."""
        return cls(
            region=os.getenv('AWS_REGION', 'us-east-1'),
            bedrock_model_id=os.getenv('AWS_BEDROCK_MODEL_ID', 'us.anthropic.claude-opus-4-7'),
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )
