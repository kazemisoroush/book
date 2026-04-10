"""Full-pipeline TTS workflow: download, parse, AI-segment, assign voices, synthesise audio."""
from pathlib import Path
from typing import Optional

import structlog

from src.domain.models import Book
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.tts.tts_provider import TTSProvider
from src.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.config.feature_flags import FeatureFlags
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
        voice_entries: list[VoiceEntry],
        tts_provider: TTSProvider,
        elevenlabs_client: object | None = None,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialise with explicit dependencies.

        Args:
            ai_workflow: Workflow that downloads and AI-segments the book.
            voice_entries: List of available ElevenLabs voices.
            tts_provider: TTS provider for audio synthesis.
            elevenlabs_client: Optional ElevenLabs SDK client for voice design.
            books_dir: Base directory for book output (default: ``books/``).
        """
        self._ai_workflow = ai_workflow
        self._voice_entries = voice_entries
        self._tts_provider = tts_provider
        self._elevenlabs_client = elevenlabs_client
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
        from src.config import get_config
        from src.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider

        api_key = get_config().elevenlabs_api_key
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY not set — configure via environment variable")
        provider = ElevenLabsTTSProvider(api_key=api_key)

        # Fetch voices from ElevenLabs and wrap in VoiceEntry objects
        raw_voices = provider.get_voices()
        voices = [
            VoiceEntry(
                voice_id=v["voice_id"],
                name=v["name"],
                labels=v["labels"],
            )
            for v in raw_voices
        ]
        if not voices:
            raise RuntimeError("No voices available from ElevenLabs")

        # For voice design, we still need the ElevenLabs client
        # This is a temporary workaround until voice design is refactored
        # to go through the provider interface (future work).
        elevenlabs_client = provider._get_client() if isinstance(provider, ElevenLabsTTSProvider) else None

        repository = FileBookRepository(base_dir=str(books_dir))
        ai_workflow = AIProjectGutenbergWorkflow.create(repository=repository)

        return cls(
            ai_workflow=ai_workflow,
            voice_entries=voices,
            tts_provider=provider,
            elevenlabs_client=elevenlabs_client,
            books_dir=books_dir,
        )

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: int | None = None,
        reparse: bool = False,
        debug: bool = False,
        feature_flags: Optional[FeatureFlags] = None,
    ) -> Book:
        """Run the full pipeline and synthesise audio for each chapter.

        Steps:
        1. Download and AI-segment the book (from start_chapter to end_chapter).
        2. Assign ElevenLabs voices to every character in the registry.
        3. Synthesise audio into ``{books_dir}/{book_id}/audio/``.

        Args:
            url: Project Gutenberg book URL.
            start_chapter: 1-based chapter index to begin parsing (default: 1).
                          If 1 and cached partial book exists and reparse=False,
                          auto-resumes from the last cached chapter.
            end_chapter: 1-based chapter index to end parsing (inclusive).
                        Default: None (parse all chapters in the book).
            reparse: When ``True``, bypass cached parsed book and re-run
                     the AI pipeline.  Defaults to ``False``.
            debug: When ``True``, keep individual segment MP3 files alongside
                   the stitched ``chapter.mp3``.  Defaults to ``False``.
            feature_flags: Feature toggles controlling ambient, SFX, emotion,
                          voice design, and scene context.  Defaults to all-enabled.

        Returns:
            The ``Book`` produced by the AI parse (with ``character_registry``
            populated).
        """
        logger.info(
            "tts_workflow_started",
            url=url,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
        )

        # Step 1: Download + AI segment
        book = self._ai_workflow.run(
            url,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            reparse=reparse,
        )

        # Step 2: Compute output directory from book metadata
        book_id = generate_book_id(book.metadata)
        audio_dir = self._books_dir / book_id / "audio"
        flags = feature_flags or FeatureFlags()
        tts_orchestrator = TTSOrchestrator(
            provider=self._tts_provider,
            output_dir=audio_dir,
            debug=debug,
            feature_flags=flags,
        )

        logger.info("tts_audio_dir", book_id=book_id, audio_dir=str(audio_dir))

        # Step 3: Assign voices
        # Create VoiceAssigner with voice registry if voice design is enabled
        if flags.voice_design_enabled and self._elevenlabs_client is not None:
            from src.tts.voice_registry import ElevenLabsVoiceRegistry
            registry = ElevenLabsVoiceRegistry(self._elevenlabs_client)
            voice_assigner = VoiceAssigner(
                self._voice_entries,
                voice_registry=registry,
                book_title=book.metadata.title,
                book_author=book.metadata.author or "",
            )
        else:
            voice_assigner = VoiceAssigner(self._voice_entries)

        voice_assignment = voice_assigner.assign(book.character_registry)

        logger.info(
            "tts_workflow_voice_assignment_done",
            character_count=len(voice_assignment),
        )

        # Step 4: Synthesise each chapter
        chapters = book.content.chapters
        for chapter in chapters:
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

        logger.info("tts_workflow_complete", url=url, chapters=len(chapters))
        return book
