"""Load provider tokens from AWS Secrets Manager into the environment (cloud only)."""
import json
import os
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

_SECRET_ARN_ENV = "PROVIDER_SECRET_ARN"


def load_provider_secret(client: Optional[Any] = None) -> None:
    """Export each token from the provider secret into ``os.environ``.

    A no-op when PROVIDER_SECRET_ARN is unset, so local runs keep using .env. The secret is a
    JSON object mapping environment variable names to values, for example
    ``{"CLAUDE_CODE_OAUTH_TOKEN": "..."}``. The worker calls this before running a workflow so
    that Config.from_env picks the tokens up.
    """
    secret_arn = os.getenv(_SECRET_ARN_ENV)
    if not secret_arn:
        return
    if client is None:
        import boto3
        client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    tokens = json.loads(response["SecretString"])
    for key, value in tokens.items():
        os.environ[key] = value
    logger.info("provider_secret_loaded", keys=sorted(tokens))
