"""Tests for loading provider tokens from Secrets Manager."""
import json
import os
from typing import Any

from src.config.provider_secrets import load_provider_secret


class _FakeSecrets:
    """A stand-in Secrets Manager client returning a fixed JSON payload."""

    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload
        self.requested: Any = None

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        self.requested = SecretId
        return {"SecretString": json.dumps(self._payload)}


def test_no_op_without_secret_arn(monkeypatch) -> None:
    # Arrange
    monkeypatch.delenv("PROVIDER_SECRET_ARN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    fake = _FakeSecrets({"CLAUDE_CODE_OAUTH_TOKEN": "should-not-load"})

    # Act
    load_provider_secret(client=fake)

    # Assert
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in os.environ
    assert fake.requested is None


class _EmptySecret:
    """A client returning a secret that exists but has no value yet."""

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        return {"SecretString": ""}


def test_no_op_when_secret_is_empty(monkeypatch) -> None:
    # Arrange: the secret exists (ARN set) but has not been populated.
    monkeypatch.setenv("PROVIDER_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:1:secret:x")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    # Act
    load_provider_secret(client=_EmptySecret())

    # Assert: no crash, nothing exported
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in os.environ


class _GarbageSecret:
    """A client returning a non-JSON secret value (the CDK auto-generated placeholder)."""

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        return {"SecretString": "WitDC)8->EO(!qn3,5K/WW@?*gW2)P_}"}


def test_no_op_when_secret_is_not_json(monkeypatch) -> None:
    # Arrange
    monkeypatch.setenv("PROVIDER_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:1:secret:x")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    # Act
    load_provider_secret(client=_GarbageSecret())

    # Assert: no crash, nothing exported
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in os.environ


def test_exports_tokens_into_environ(monkeypatch) -> None:
    # Arrange
    monkeypatch.setenv("PROVIDER_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:1:secret:x")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    fake = _FakeSecrets({"CLAUDE_CODE_OAUTH_TOKEN": "tok-123", "ELEVENLABS_API_KEY": "el-9"})

    # Act
    load_provider_secret(client=fake)

    # Assert
    assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-123"
    assert os.environ["ELEVENLABS_API_KEY"] == "el-9"
    assert fake.requested.endswith(":secret:x")
