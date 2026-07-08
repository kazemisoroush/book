"""Configuration for the local API server."""
import os
from dataclasses import dataclass, field
from typing import Optional

_DEFAULT_ORIGINS = ("http://localhost:3000",)


@dataclass
class ApiConfig:
    """Bind address, allowed origins, and (in the cloud) the worker the API dispatches runs to."""
    host: str
    port: int
    allowed_origins: list[str] = field(default_factory=lambda: list(_DEFAULT_ORIGINS))
    worker_function_name: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'ApiConfig':
        """Load the API bind address, allowed origins, and worker function from the environment."""
        return cls(
            host=os.getenv('API_HOST', '127.0.0.1'),
            port=int(os.getenv('API_PORT', '8000')),
            allowed_origins=_origins_from_env(),
            worker_function_name=os.getenv('WORKER_FUNCTION_NAME'),
        )


def _origins_from_env() -> list[str]:
    raw = os.getenv('API_ALLOWED_ORIGINS')
    if not raw:
        return list(_DEFAULT_ORIGINS)
    return [origin.strip() for origin in raw.split(',') if origin.strip()]
