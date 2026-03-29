"""Full-pipeline TTS workflow: download, parse, AI-segment, assign voices, synthesise audio."""
from pathlib import Path

import structlog

from src.domain.models import Book
from src.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.tts.tts_orchestrator import TTSOrchestrator
from src.workflows.workflow import Workflow
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow

logger = structlog.get_logger(__name__)


class TTSProjectGutenbergWorkflow(Workflow):
    """End-to-end workflow: download, AI-parse, assign voices, synthesise audio.

    This workflow orchestrates the full pipeline:
    1. Download + AI section segmentation (delegated to AIProjectGutenbergWorkflow)
    2. Voice assignment via VoiceAssigner
    3. TTS synthesis via TTSOrchestrator for every chapter in scope

    Audio files are a side effect written to ``output_dir``.  The workflow
    returns the ``Book`` produced by the AI parse so callers can inspect the
    structured data.

    Use :meth:`create` to get an instance wired with production dependencies.
    """

    def __init__(
        self,
        ai_workflow: AIProjectGutenbergWorkflow,
        voice_assigner: VoiceAssigner,
        tts_orchestrator: TTSOrchestrator,
        output_dir: Path,
    ) -> None:
        """Initialise with explicit dependencies.

        Args:
            ai_workflow: Workflow that downloads and AI-segments the book.
            voice_assigner: Assigns ElevenLabs voices to characters.
            tts_orchestrator: Synthesises audio for each chapter.
            output_dir: Directory where audio files (and book.json) are written.
        """
        self._ai_workflow = ai_workflow
        self._voice_assigner = voice_assigner
        self._tts_orchestrator = tts_orchestrator
        self._output_dir = output_dir

    @classmethod
    def create(cls, output_dir: Path) -> "TTSProjectGutenbergWorkflow":
        """Factory that wires all production dependencies.

        Requires:
        - ``ELEVENLABS_API_KEY`` environment variable (raises ``KeyError`` if absent)
        - AWS credentials for Bedrock (same as AIProjectGutenbergWorkflow.create())

        Args:
            output_dir: Directory where audio files are written.

        Returns:
            A fully-wired ``TTSProjectGutenbergWorkflow``.
        """
        import os
        from src.tts.elevenlabs_provider import ElevenLabsProvider

        api_key = os.environ["ELEVENLABS_API_KEY"]
        provider = ElevenLabsProvider(api_key=api_key)

        # Fetch voices from ElevenLabs and wrap in VoiceEntry objects
        raw_voices = provider._get_client().voices.get_all()
        voices = [
            VoiceEntry(
                voice_id=v.voice_id,
                name=v.name,
                labels=dict(v.labels) if v.labels else {},
            )
            for v in raw_voices.voices
        ]
        if not voices:
            raise RuntimeError("No voices available from ElevenLabs")

        ai_workflow = AIProjectGutenbergWorkflow.create()
        voice_assigner = VoiceAssigner(voices)
        tts_orchestrator = TTSOrchestrator(provider=provider, output_dir=output_dir)

        return cls(
            ai_workflow=ai_workflow,
            voice_assigner=voice_assigner,
            tts_orchestrator=tts_orchestrator,
            output_dir=output_dir,
        )

    def run(self, url: str, chapter_limit: int = 3) -> Book:
        """Run the full pipeline and synthesise audio for each chapter.

        Steps:
        1. Download and AI-segment the book (up to ``chapter_limit`` chapters).
        2. Assign ElevenLabs voices to every character in the registry.
        3. Synthesise audio for each chapter via TTSOrchestrator.

        Audio files are written to ``output_dir`` as a side effect.

        Args:
            url: Project Gutenberg book URL.
            chapter_limit: Maximum chapters to process. ``0`` = all. Defaults to 3.

        Returns:
            The ``Book`` produced by the AI parse (with ``character_registry``
            populated).
        """
        logger.info("tts_workflow_started", url=url, chapter_limit=chapter_limit)

        # Step 1: Download + AI segment
        book = self._ai_workflow.run(url, chapter_limit=chapter_limit)

        # Step 2: Assign voices
        voice_assignment = self._voice_assigner.assign(book.character_registry)

        logger.info(
            "tts_workflow_voice_assignment_done",
            character_count=len(voice_assignment),
        )

        # Step 3: Synthesise each chapter
        for chapter in book.content.chapters:
            logger.info(
                "tts_workflow_synthesising_chapter",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
            )
            self._tts_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chapter.number,
                voice_assignment=voice_assignment,
            )

        logger.info("tts_workflow_complete", url=url, chapters=len(book.content.chapters))
        return book
