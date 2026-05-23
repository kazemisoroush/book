"""CLI argument configuration for workflow execution."""
import argparse
from dataclasses import dataclass
from typing import Optional


@dataclass
class CLIConfig:
    """CLI argument configuration for workflow execution.

    Parses command-line arguments and provides a clean interface
    for main.py to dispatch to workflows.

    Feature flags are NOT part of CLIConfig; they live in
    ``src/config/feature_flags.py`` and are hardcoded at module level.
    """
    workflow: str
    url: Optional[str] = None
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    debug: bool = False
    provider: Optional[str] = None

    @classmethod
    def from_cli(cls) -> 'CLIConfig':
        """Parse CLI arguments and return a CLIConfig instance.

        Returns:
            CLIConfig instance with values from command-line arguments
        """
        parser = argparse.ArgumentParser(
            description="Run a book-processing workflow.",
        )
        parser.add_argument(
            "--workflow",
            choices=["parse", "ai", "tts", "ambient", "sfx", "music", "mix"],
            default="ai",
            help="Workflow to run (default: ai)",
        )
        parser.add_argument(
            "--url",
            default=None,
            help="Project Gutenberg zip URL (required for parse/ai/tts/ambient/sfx/music/mix)"
        )
        parser.add_argument(
            "--start-chapter",
            type=int,
            default=1,
            help="1-based start chapter (default: 1)"
        )
        parser.add_argument(
            "--end-chapter",
            type=int,
            default=None,
            help="1-based end chapter (inclusive)"
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            default=False,
            help="Bypass cache and re-run the workflow stage from scratch"
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            default=False,
            help="Keep individual beat MP3 files"
        )
        parser.add_argument(
            "--provider",
            default=None,
            help=(
                "Override the default backend for the chosen workflow. "
                "ai: anthropic|bedrock. tts: elevenlabs|fish. "
                "ambient/sfx: audiogen|elevenlabs."
            ),
        )

        args = parser.parse_args()

        config = cls(
            workflow=args.workflow,
            url=args.url,
            start_chapter=args.start_chapter,
            end_chapter=args.end_chapter,
            refresh=args.refresh,
            debug=args.debug,
            provider=args.provider,
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Validate the CLI configuration.

        Raises:
            ValueError: If a required field is missing for the chosen workflow.
        """
        if self.url is None:
            raise ValueError(f"--url is required for --workflow {self.workflow}")
