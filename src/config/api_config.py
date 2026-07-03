"""Configuration for the local API server."""
import os
from dataclasses import dataclass


@dataclass
class ApiConfig:
    """Bind address for the local API server."""
    host: str
    port: int

    @classmethod
    def from_env(cls) -> 'ApiConfig':
        """Load the API bind address from environment variables."""
        return cls(
            host=os.getenv('API_HOST', '127.0.0.1'),
            port=int(os.getenv('API_PORT', '8000')),
        )
