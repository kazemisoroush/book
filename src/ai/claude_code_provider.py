"""Claude Code AI provider that runs the CLI in print mode on the signed-in plan."""
import json
import os
import subprocess

from ..config import Config
from .ai_provider import AIProvider

_CONTROL_ENV_PREFIX = "CLAUDE_CODE_"
_CONTROL_ENV_KEYS = frozenset({"CLAUDECODE", "AI_AGENT"})
_OAUTH_TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"


class ClaudeCodeProvider(AIProvider):
    """AI provider that runs through the Claude Code CLI in print mode."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.model_id = "claude-code"

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:  # noqa: ARG002
        result = subprocess.run(
            ["claude", "--print", "--output-format", "json", "--effort", "low"],
            input=prompt,
            capture_output=True,
            text=True,
            env=self._cli_env(),
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no detail"
            raise RuntimeError(
                f"claude-code CLI failed (exit {result.returncode}): {detail}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"claude-code returned non-JSON output: {result.stdout[:200]!r}"
            ) from exc
        if payload.get("is_error"):
            raise RuntimeError(
                f"claude-code returned an error: {payload.get('result')}"
            )
        if "result" not in payload:
            raise RuntimeError(f"claude-code output has no result field: {payload!r}")
        return payload["result"]

    def _cli_env(self) -> dict[str, str]:
        """Build the CLI subprocess environment, injecting the token from config."""
        env = self._child_env()
        if self.config.claude_code_oauth_token:
            env[_OAUTH_TOKEN_ENV] = self.config.claude_code_oauth_token
        return env

    @staticmethod
    def _child_env() -> dict[str, str]:
        """Return the ambient environment with the Claude Code control variables removed."""
        return {
            key: value
            for key, value in os.environ.items()
            if key not in _CONTROL_ENV_KEYS
            and not key.startswith(_CONTROL_ENV_PREFIX)
        }
