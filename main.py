"""Main entry point for audiobook generator."""
import argparse
import json
import os
import sys
from pathlib import Path

import structlog

from src.config.logging_config import configure
from src.workflows.project_gutenberg_workflow import (
    ProjectGutenbergWorkflow
)
from src.workflows.ai_project_gutenberg_workflow import (
    AIProjectGutenbergWorkflow
)
from src.tts.elevenlabs_provider import ElevenLabsProvider
from src.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.tts.tts_orchestrator import TTSOrchestrator

logger = structlog.get_logger(__name__)


def main() -> None:
    """Main entry point - parse CLI arguments and execute workflow."""
    # Configure structured logging before anything else
    configure()

    parser = argparse.ArgumentParser(
        description='Parse Project Gutenberg books into JSON or generate TTS audio'
    )
    parser.add_argument(
        'url',
        help='Project Gutenberg book URL (e.g., https://www.gutenberg.org/files/123/123-h.zip)'  # noqa: E501
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file path (if not specified, prints to stdout)',
        default=None
    )
    parser.add_argument(
        '--tts',
        action='store_true',
        help=(
            'Run the full TTS pipeline: download → AI parse → assign voices → '
            'synthesise Chapter 1 → output/chapter_01.mp3.  '
            'Requires ELEVENLABS_API_KEY environment variable.'
        )
    )

    args = parser.parse_args()

    if args.tts:
        _run_tts_pipeline(args.url)
    else:
        _run_parse_pipeline(args.url, args.output)


def _run_parse_pipeline(url: str, output: str | None) -> None:
    """Run the static parse pipeline and output JSON."""
    workflow = ProjectGutenbergWorkflow.create()

    try:
        book = workflow.run(url)

        # Convert to JSON
        json_output = json.dumps(book.to_dict(), indent=2, ensure_ascii=False)

        # Output to file or stdout — this is data output, not a log message
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(json_output)
        else:
            print(json_output)

    except Exception as e:
        logger.error("workflow_error", error=str(e), exc_info=True)
        sys.exit(1)


def _run_tts_pipeline(url: str) -> None:
    """Run the full TTS pipeline: download → AI parse → synthesise Chapter 1."""
    # --- Validate ELEVENLABS_API_KEY ---
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error(
            "tts_missing_api_key",
            reason="ELEVENLABS_API_KEY environment variable is not set",
            hint="Export ELEVENLABS_API_KEY=<your-key> before running --tts",
        )
        print(
            "Error: ELEVENLABS_API_KEY environment variable is required for --tts.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Step 1: Download and AI-parse the book (chapter 1 only)
        logger.info("tts_pipeline_start", url=url)
        workflow = AIProjectGutenbergWorkflow.create(chapter_limit=1)
        book = workflow.run(url)

        # Step 2: Set up ElevenLabs provider and get available voices
        provider = ElevenLabsProvider(api_key=api_key)
        voices_dict = provider.get_available_voices()
        # Convert raw {name: voice_id} dict into VoiceEntry list
        voice_entries = [
            VoiceEntry(voice_id=vid, name=name, labels={})
            for name, vid in voices_dict.items()
        ]

        # Step 3: Assign voices to characters
        assigner = VoiceAssigner(voice_entries)
        voice_assignment = assigner.assign(book.character_registry)

        # Step 4: Synthesise Chapter 1
        output_dir = Path("output")
        orchestrator = TTSOrchestrator(provider, output_dir)
        output_path = orchestrator.synthesize_chapter(book, 1, voice_assignment)

        logger.info("tts_pipeline_done", output=str(output_path))
        print(str(output_path))

    except Exception as e:
        logger.error("tts_pipeline_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
