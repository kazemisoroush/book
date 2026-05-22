"""Anthropic direct API configuration for the audiobook generator."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AnthropicConfig:
    """Anthropic direct API configuration."""
    api_key: Optional[str]
    model_id: str

    @classmethod
    def from_env(cls) -> 'AnthropicConfig':
        """Load Anthropic configuration from environment variables."""
        return cls(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            model_id=os.getenv('ANTHROPIC_MODEL_ID', 'claude-opus-4-5-20251101'),
        )
