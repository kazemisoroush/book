"""Load provider tokens from AWS Secrets Manager into the environment (cloud only)."""
import json
import os
from typing import Any, Optional

import structlog

from src.config.secrets_config import SecretsConfig

logger = structlog.get_logger(__name__)


def load_provider_secret(
    config: Optional[SecretsConfig] = None,
    client: Optional[Any] = None,
) -> None:
    """Export each token from the provider secret into ``os.environ``.

    A no-op when no provider secret is configured, so local runs keep using .env. The secret is
    a JSON object mapping environment variable names to values, for example
    ``{"CLAUDE_CODE_OAUTH_TOKEN": "..."}``. The worker calls this before running a workflow so
    that Config.from_env picks the tokens up.
    """
    config = config or SecretsConfig.from_env()
    if not config.provider_secret_arn:
        return
    if client is None:
        import boto3
        client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=config.provider_secret_arn)
    tokens = json.loads(response["SecretString"])
    for key, value in tokens.items():
        os.environ[key] = value
    logger.info("provider_secret_loaded", keys=sorted(tokens))
