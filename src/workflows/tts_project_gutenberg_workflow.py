"""Full-pipeline TTS workflow: download, parse, AI-segment, assign voices, synthesise audio."""
from pathlib import Path

import structlog

from src.domain.models import Book
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.tts.tts_provider import TTSProvider
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

    Audio files are written to ``{books_dir}/{book_id}/audio/``.  The workflow
    returns the ``Book`` produced by the AI parse so callers can inspect the
    structured data.

    Use :meth:`create` to get an instance wired with production dependencies.
    """

    def __init__(
        self,
        ai_workflow: AIProjectGutenbergWorkflow,
        voice_assigner: VoiceAssigner,
        tts_provider: TTSProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialise with explicit dependencies.

        Args:
            ai_workflow: Workflow that downloads and AI-segments the book.
            voice_assigner: Assigns ElevenLabs voices to characters.
            tts_provider: TTS provider for audio synthesis.
            books_dir: Base directory for book output (default: ``books/``).
        """
        self._ai_workflow = ai_workflow
        self._voice_assigner = voice_assigner
        self._tts_provider = tts_provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "TTSProjectGutenbergWorkflow":
        """Factory that wires all production dependencies.

        Requires:
        - ``ELEVENLABS_API_KEY`` environment variable (raises ``KeyError`` if absent)
        - AWS credentials for Bedrock (same as AIProjectGutenbergWorkflow.create())

        Args:
            books_dir: Base directory for book output (default: ``books/``).

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

        elevenlabs_client = provider._get_client()

        repository = FileBookRepository(base_dir=str(books_dir))
        ai_workflow = AIProjectGutenbergWorkflow.create(repository=repository)
        voice_assigner = VoiceAssigner(voices, elevenlabs_client=elevenlabs_client)

        return cls(
            ai_workflow=ai_workflow,
            voice_assigner=voice_assigner,
            tts_provider=provider,
            books_dir=books_dir,
        )

    def run(
        self, url: str, chapter_limit: int = 3, reparse: bool = False, debug: bool = False,
    ) -> Book:
        """Run the full pipeline and synthesise audio for each chapter.

        Steps:
        1. Download and AI-segment the book (up to ``chapter_limit`` chapters).
        2. Assign ElevenLabs voices to every character in the registry.
        3. Synthesise audio into ``{books_dir}/{book_id}/audio/``.

        Args:
            url: Project Gutenberg book URL.
            chapter_limit: Maximum chapters to process. ``0`` = all. Defaults to 3.
            reparse: When ``True``, bypass cached parsed book and re-run
                     the AI pipeline.  Defaults to ``False``.
            debug: When ``True``, keep individual segment MP3 files alongside
                   the stitched ``chapter.mp3``.  Defaults to ``False``.

        Returns:
            The ``Book`` produced by the AI parse (with ``character_registry``
            populated).
        """
        logger.info("tts_workflow_started", url=url, chapter_limit=chapter_limit)

        # Step 1: Download + AI segment
        book = self._ai_workflow.run(url, chapter_limit=chapter_limit, reparse=reparse)

        # Step 2: Compute output directory from book metadata
        book_id = generate_book_id(book.metadata)
        audio_dir = self._books_dir / book_id / "audio"
        tts_orchestrator = TTSOrchestrator(
            provider=self._tts_provider, output_dir=audio_dir, debug=debug,
        )

        logger.info("tts_audio_dir", book_id=book_id, audio_dir=str(audio_dir))

        # Step 3: Assign voices
        voice_assignment = self._voice_assigner.assign(book.character_registry)

        logger.info(
            "tts_workflow_voice_assignment_done",
            character_count=len(voice_assignment),
        )

        # Step 4: Synthesise each chapter
        for chapter in book.content.chapters:
            logger.info(
                "tts_workflow_synthesising_chapter",
                chapter_number=chapter.number,
                chapter_title=chapter.title,
            )
            tts_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chapter.number,
                voice_assignment=voice_assignment,
            )

        logger.info("tts_workflow_complete", url=url, chapters=len(book.content.chapters))
        return book
