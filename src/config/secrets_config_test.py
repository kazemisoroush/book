"""Tests for SecretsConfig."""
from src.config.secrets_config import SecretsConfig


def test_reads_provider_secret_arn(monkeypatch) -> None:
    # Arrange / Act
    monkeypatch.setenv("PROVIDER_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:1:secret:x")

    # Assert
    arn = SecretsConfig.from_env().provider_secret_arn
    assert arn is not None and arn.endswith(":secret:x")


def test_defaults_to_none(monkeypatch) -> None:
    # Arrange / Act
    monkeypatch.delenv("PROVIDER_SECRET_ARN", raising=False)

    # Assert
    assert SecretsConfig.from_env().provider_secret_arn is None
