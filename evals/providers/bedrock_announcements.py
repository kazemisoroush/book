"""Custom promptfoo provider for the AnnouncementFormatter pipeline.

This provider calls the real AnnouncementFormatter + AWSBedrockProvider stack,
exactly as the application does, so promptfoo evals test the actual
prompt+model combination.

promptfoo invokes ``call_api(prompt, options, context)`` and expects
a dict back with ``{"output": ...}``.
"""
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so ``src.*`` imports work.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.ai.aws_bedrock_provider import AWSBedrockProvider  # noqa: E402
from src.config.config import Config  # noqa: E402
from src.parsers.announcement_formatter import AnnouncementFormatter  # noqa: E402


def call_api(
    prompt: str,
    options: dict,  # type: ignore[type-arg]
    context: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Run a book title or chapter announcement through the formatter.

    ``context["vars"]`` must contain either:
      - ``raw_title`` + ``raw_author`` (for book title formatting)
      - ``chapter_number`` + ``chapter_title`` (for chapter announcement)

    The provider auto-detects which mode based on which vars are present.
    """
    vars_ = context.get("vars", {})

    config = Config.from_env()
    ai_provider = AWSBedrockProvider(config)
    formatter = AnnouncementFormatter(ai_provider)

    if "raw_title" in vars_:
        result = formatter.format_book_title(
            vars_["raw_title"],
            vars_.get("raw_author"),
        )
    elif "chapter_number" in vars_:
        result = formatter.format_chapter_announcement(
            int(vars_["chapter_number"]),
            vars_["chapter_title"],
        )
    else:
        return {"error": "Missing required vars: need raw_title or chapter_number"}

    return {"output": result}
