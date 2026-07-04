"""Claude Code AI provider that runs the Claude Code CLI in print mode.

Shells out to ``claude --print --output-format json``, which reuses the CLI's
OAuth session on the host so calls bill against the signed-in Pro/Max plan
rather than an API key. The Claude Code control environment is stripped from
the child process, so a run nested inside a Claude Code session starts its own
top-level session instead of trying to attach to the parent's control channel.

Tradeoffs vs :class:`AnthropicProvider`:

* No Anthropic-style prompt caching at the wire level.
* Quota-billed: Pro caps around 45 messages per 5h; Max scales that.
* Requires Claude Code installed and authenticated on the host.
"""
import json
import os
import subprocess

from ..config import Config
from .ai_provider import AIProvider

_CONTROL_ENV_PREFIX = "CLAUDE_CODE_"
_CONTROL_ENV_KEYS = frozenset({"CLAUDECODE", "AI_AGENT"})


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
            env=self._child_env(),
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no detail"
            raise RuntimeError(
                f"claude-code CLI failed (exit {result.returncode}): {detail}"
            )
        payload = json.loads(result.stdout)
        if payload.get("is_error"):
            raise RuntimeError(
                f"claude-code returned an error: {payload.get('result')}"
            )
        return _strip_code_fence(payload["result"])

    @staticmethod
    def _child_env() -> dict[str, str]:
        """Return the environment with the Claude Code control variables removed."""
        return {
            key: value
            for key, value in os.environ.items()
            if key not in _CONTROL_ENV_KEYS
            and not key.startswith(_CONTROL_ENV_PREFIX)
        }


def _strip_code_fence(text: str) -> str:
    """Return *text* with a wrapping markdown code fence removed, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
