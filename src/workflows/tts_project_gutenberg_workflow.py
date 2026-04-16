"""Full-pipeline TTS workflow: download, parse, AI-segment, assign voices, synthesise audio."""
from pathlib import Path
from typing import Optional

import structlog

from src.domain.models import Book
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.audio.tts.tts_provider import TTSProvider
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.music.music_provider import MusicProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.ambient.stable_audio_ambient_provider import StableAudioAmbientProvider
from src.audio.music.suno_music_provider import SunoMusicProvider
from src.audio.tts.voice_assigner import VoiceAssigner
from src.config.feature_flags import FeatureFlags
from src.audio.audio_orchestrator import AudioOrchestrator
from src.workflows.workflow import Workflow
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow

logger = structlog.get_logger(__name__)


class TTSProjectGutenbergWorkflow(Workflow):
    """End-to-end workflow: download, AI-parse, assign voices, synthesise audio.

    This workflow orchestrates the full pipeline:
    1. Download + AI section segmentation (delegated to AIProjectGutenbergWorkflow)
    2. Voice assignment via VoiceAssigner
    3. Audio synthesis via AudioOrchestrator for every chapter in scope

    Audio files are written to ``{books_dir}/{book_id}/audio/``.  The workflow
    returns the ``Book`` produced by the AI parse so callers can inspect the
    structured data.

    Use :meth:`create` to get an instance wired with production dependencies.
    """

    def __init__(
        self,
        ai_workflow: AIProjectGutenbergWorkflow,
        tts_provider: TTSProvider,
        ambient_provider: Optional[AmbientProvider] = None,
        music_provider: Optional[MusicProvider] = None,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialise with explicit dependencies.

        Args:
            ai_workflow: Workflow that downloads and AI-segments the book.
            tts_provider: TTS provider for audio synthesis.  Voice fetching
                          is handled internally by :class:`VoiceAssigner`.
            ambient_provider: Optional ambient sound provider.
            music_provider: Optional music provider.
            books_dir: Base directory for book output (default: ``books/``).
        """
        self._ai_workflow = ai_workflow
        self._tts_provider = tts_provider
        self._ambient_provider = ambient_provider
        self._music_provider = music_provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "TTSProjectGutenbergWorkflow":
        """Factory that wires all production dependencies.

        Requires:
        - ``FISH_AUDIO_API_KEY`` environment variable for TTS
        - ``STABILITY_API_KEY`` environment variable for ambient sound (optional)
        - ``SUNO_API_KEY`` environment variable for music (optional)
        - AWS credentials for Bedrock (same as AIProjectGutenbergWorkflow.create())

        Args:
            books_dir: Base directory for book output (default: ``books/``).

        Returns:
            A fully-wired ``TTSProjectGutenbergWorkflow``.
        """
        from src.config import get_config

        config = get_config()

        # Instantiate Fish Audio TTS provider
        fish_api_key = config.fish_audio_api_key
        if not fish_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set — configure via environment variable")
        tts_provider = FishAudioTTSProvider(api_key=fish_api_key)

        # Instantiate Stable Audio ambient provider (optional)
        ambient_provider: Optional[AmbientProvider] = None
        if config.stability_api_key:
            cache_dir = books_dir / "cache" / "ambient"
            ambient_provider = StableAudioAmbientProvider(
                api_key=config.stability_api_key,
                cache_dir=cache_dir,
            )

        # Instantiate Suno music provider (optional)
        music_provider: Optional[MusicProvider] = None
        if config.suno_api_key:
            cache_dir = books_dir / "cache" / "music"
            music_provider = SunoMusicProvider(
                api_key=config.suno_api_key,
                cache_dir=cache_dir,
            )

        repository = FileBookRepository(base_dir=str(books_dir))
        ai_workflow = AIProjectGutenbergWorkflow.create(repository=repository)

        return cls(
            ai_workflow=ai_workflow,
            tts_provider=tts_provider,
            ambient_provider=ambient_provider,
            music_provider=music_provider,
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
            feature_flags: Feature toggles controlling ambient, sound effects, emotion,
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

        flags = feature_flags or FeatureFlags()

        # Step 1: Download + AI segment
        book = self._ai_workflow.run(
            url,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            reparse=reparse,
            feature_flags=flags,
        )

        # Step 2: Compute output directory from book metadata
        book_id = generate_book_id(book.metadata)
        audio_dir = self._books_dir / book_id / "audio"
        audio_orchestrator = AudioOrchestrator(
            provider=self._tts_provider,
            output_dir=audio_dir,
            debug=debug,
            feature_flags=flags,
        )

        logger.info("tts_audio_dir", book_id=book_id, audio_dir=str(audio_dir))

        # Step 3: Assign voices
        voice_assigner = VoiceAssigner(self._tts_provider)

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
            audio_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chapter.number,
                voice_assignment=voice_assignment,
            )

        logger.info("tts_workflow_complete", url=url, chapters=len(chapters))
        return book
