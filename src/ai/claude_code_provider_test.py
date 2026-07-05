"""Tests for ClaudeCodeProvider."""
import json
import subprocess

from src.ai.claude_code_provider import ClaudeCodeProvider
from src.config import Config


def _provider() -> ClaudeCodeProvider:
    return ClaudeCodeProvider(Config.from_env())


def test_generate_returns_cli_result(monkeypatch):
    # Arrange
    payload = {"is_error": False, "result": "{\"chapters\": []}"}
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Act
    result = _provider().generate("parse this chapter")

    # Assert
    assert result == "{\"chapters\": []}"
    assert captured["cmd"][:2] == ["claude", "--print"]
    assert "--effort" in captured["cmd"]
    assert captured["input"] == "parse this chapter"


def test_generate_raises_on_nonzero_exit(monkeypatch):
    # Arrange
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Act / Assert
    try:
        _provider().generate("prompt")
        raised = False
    except RuntimeError as exc:
        raised = "not logged in" in str(exc)
    assert raised


def test_generate_raises_on_error_payload(monkeypatch):
    # Arrange
    payload = {"is_error": True, "result": "quota exceeded"}

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Act / Assert
    try:
        _provider().generate("prompt")
        raised = False
    except RuntimeError as exc:
        raised = "quota exceeded" in str(exc)
    assert raised


def test_generate_raises_on_non_json_stdout(monkeypatch):
    # Arrange
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="not json at all", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Act / Assert
    try:
        _provider().generate("prompt")
        raised = False
    except RuntimeError as exc:
        raised = "non-JSON" in str(exc)
    assert raised


def test_generate_raises_when_result_field_missing(monkeypatch):
    # Arrange
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="{\"is_error\": false}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Act / Assert
    try:
        _provider().generate("prompt")
        raised = False
    except RuntimeError as exc:
        raised = "no result field" in str(exc)
    assert raised


def test_child_env_strips_claude_code_control_vars(monkeypatch):
    # Arrange
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SSE_PORT", "20505")
    monkeypatch.setenv("AI_AGENT", "claude-code_agent")
    monkeypatch.setenv("PATH", "/usr/bin")

    # Act
    env = ClaudeCodeProvider._child_env()

    # Assert
    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_SSE_PORT" not in env
    assert "AI_AGENT" not in env
    assert env["PATH"] == "/usr/bin"


def test_child_env_keeps_the_oauth_token(monkeypatch):
    # Arrange
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok-123")
    monkeypatch.setenv("CLAUDE_CODE_SSE_PORT", "20505")
    monkeypatch.setenv("CLAUDECODE", "1")

    # Act
    env = ClaudeCodeProvider._child_env()

    # Assert
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-123"
    assert "CLAUDE_CODE_SSE_PORT" not in env
    assert "CLAUDECODE" not in env
