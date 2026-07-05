"""Configuration for the local API server."""
import os
from dataclasses import dataclass, field

_DEFAULT_ORIGINS = ("http://localhost:3000",)


@dataclass
class ApiConfig:
    """Bind address and allowed browser origins for the local API server."""
    host: str
    port: int
    allowed_origins: list[str] = field(default_factory=lambda: list(_DEFAULT_ORIGINS))

    @classmethod
    def from_env(cls) -> 'ApiConfig':
        """Load the API bind address and allowed origins from environment variables."""
        return cls(
            host=os.getenv('API_HOST', '127.0.0.1'),
            port=int(os.getenv('API_PORT', '8000')),
            allowed_origins=_origins_from_env(),
        )


def _origins_from_env() -> list[str]:
    raw = os.getenv('API_ALLOWED_ORIGINS')
    if not raw:
        return list(_DEFAULT_ORIGINS)
    return [origin.strip() for origin in raw.split(',') if origin.strip()]
