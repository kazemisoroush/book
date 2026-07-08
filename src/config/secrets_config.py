"""Config for the managed provider secret the cloud worker reads at runtime."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SecretsConfig:
    """Where the worker reads provider tokens from. Unset for local runs."""
    provider_secret_arn: Optional[str] = None

    @classmethod
    def from_env(cls) -> "SecretsConfig":
        """Read the provider secret ARN from the environment."""
        return cls(provider_secret_arn=os.getenv("PROVIDER_SECRET_ARN"))
