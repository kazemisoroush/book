"""Full-pipeline TTS workflow for testing: builds Book from embedded golden passage.

This workflow mirrors TTSProjectGutenbergWorkflow exactly but skips the
download and HTML-parse steps. Instead it accepts a GoldenE2EPassage
whose sections are embedded directly, builds a Book from those sections,
then runs the same AI-segmentation, voice-assignment, and audio-synthesis
pipeline as the production workflow.

Design notes
------------
- ``__init__`` takes an explicit ``ai_provider`` because, unlike
  ``TTSProjectGutenbergWorkflow``, there is no inner ``AIProjectGutenbergWorkflow``
  to own it.  We wire the provider here and share it between the
  ``AnnouncementFormatter`` and the ``AISectionParser``.
- ``create()`` wires all production dependencies identically to
  ``TTSProjectGutenbergWorkflow.create()`` and additionally creates an
  ``AWSBedrockProvider`` (the same AI provider used by the production
  AI workflow).
- ``run()`` mutates the chapter sections list in-place (matching
  ``AIProjectGutenbergWorkflow._inject_synthetic_sections`` behaviour).
"""
from pathlib import Path
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.ambient.stable_audio_ambient_provider import StableAudioAmbientProvider
from src.audio.audio_orchestrator import AudioOrchestrator
from src.audio.music.music_provider import MusicProvider
from src.audio.music.suno_music_provider import SunoMusicProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.config.feature_flags import FeatureFlags
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.evals.book.fixtures.golden_e2e_passage import GoldenE2EPassage
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.announcement_formatter import AnnouncementFormatter
from src.parsers.prompt_builder import PromptBuilder
from src.repository.book_id import generate_book_id
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.workflows.workflow import Workflow

logger = structlog.get_logger(__name__)


class TestWorkflow(Workflow):
    """Full-pipeline TTS workflow for testing: builds Book from embedded passage, AI-segments, assigns voices, synthesises audio.

    Identical to TTSProjectGutenbergWorkflow but skips download/parse —
    sections are provided directly via a GoldenE2EPassage.

    This workflow orchestrates:
    1. Build a Book from an embedded GoldenE2EPassage (no HTTP download).
    2. Inject synthetic book_title / chapter_announcement sections via
       ``AIProjectGutenbergWorkflow._inject_synthetic_sections``.
    3. AI-segment every non-synthetic section using ``AISectionParser``.
    4. Assign voices via ``VoiceAssigner``.
    5. Synthesise audio via ``AudioOrchestrator`` for every chapter.

    Audio files are written to ``{books_dir}/{book_id}/audio/``.

    Use :meth:`create` to get an instance wired with production dependencies.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        voice_entries: list[VoiceEntry],
        tts_provider: TTSProvider,
        ambient_provider: Optional[AmbientProvider] = None,
        music_provider: Optional[MusicProvider] = None,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialise with explicit dependencies.

        Args:
            ai_provider: AI provider used for section parsing and announcement formatting.
            voice_entries: List of available voices for assignment.
            tts_provider: TTS provider for audio synthesis.
            ambient_provider: Optional ambient sound provider.
            music_provider: Optional music provider.
            books_dir: Base directory for book output (default: ``books/``).
        """
        self._ai_provider = ai_provider
        self._voice_entries = voice_entries
        self._tts_provider = tts_provider
        self._ambient_provider = ambient_provider
        self._music_provider = music_provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "TestWorkflow":
        """Factory that wires all production dependencies.

        Wires the same providers as ``TTSProjectGutenbergWorkflow.create()``
        plus an ``AWSBedrockProvider`` for AI section parsing.

        Requires:
        - ``FISH_AUDIO_API_KEY`` environment variable for TTS
        - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` for Bedrock
        - ``STABILITY_API_KEY`` environment variable for ambient sound (optional)
        - ``SUNO_API_KEY`` environment variable for music (optional)

        Args:
            books_dir: Base directory for book output (default: ``books/``).

        Returns:
            A fully-wired ``TestWorkflow``.
        """
        from src.config.config import Config

        config = Config.from_env()

        # AI provider for section parsing + announcement formatting
        ai_provider: AIProvider = AWSBedrockProvider(config)

        # Fish Audio TTS provider
        fish_api_key = config.fish_audio_api_key
        if not fish_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set — configure via environment variable")
        tts_provider = FishAudioTTSProvider(api_key=fish_api_key)

        # Fetch voices from Fish Audio and wrap in VoiceEntry objects
        raw_voices = tts_provider.get_voices()
        voices = [
            VoiceEntry(
                voice_id=v["voice_id"],
                name=v["name"],
                labels=v["labels"],
            )
            for v in raw_voices
        ]
        if not voices:
            raise RuntimeError("No voices available from Fish Audio")

        # Stable Audio ambient provider (optional)
        ambient_provider: Optional[AmbientProvider] = None
        if config.stability_api_key:
            cache_dir = books_dir / "cache" / "ambient"
            ambient_provider = StableAudioAmbientProvider(
                api_key=config.stability_api_key,
                cache_dir=cache_dir,
            )

        # Suno music provider (optional)
        music_provider: Optional[MusicProvider] = None
        if config.suno_api_key:
            cache_dir = books_dir / "cache" / "music"
            music_provider = SunoMusicProvider(
                api_key=config.suno_api_key,
                cache_dir=cache_dir,
            )

        return cls(
            ai_provider=ai_provider,
            voice_entries=voices,
            tts_provider=tts_provider,
            ambient_provider=ambient_provider,
            music_provider=music_provider,
            books_dir=books_dir,
        )

    # Satisfy the abstract Workflow interface (url-based run is not used here)
    def run(  # type: ignore[override]
        self,
        passage: GoldenE2EPassage,
        debug: bool = False,
        feature_flags: Optional[FeatureFlags] = None,
        # Keyword arguments below satisfy the abstract signature if called generically
        url: str = "",
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        reparse: bool = False,
    ) -> Book:
        """Run the full pipeline for a golden passage and synthesise audio.

        Steps:
        1. Build a ``Book`` from the embedded passage sections.
        2. Inject synthetic book_title / chapter_announcement sections.
        3. AI-segment every non-synthetic section.
        4. Assign voices to all characters in the registry.
        5. Synthesise audio into ``{books_dir}/{book_id}/audio/``.

        Args:
            passage: Golden passage whose sections drive the pipeline.
            debug: When ``True``, keep individual segment MP3 files alongside
                   the stitched ``chapter.mp3``.  Defaults to ``False``.
            feature_flags: Feature toggles controlling ambient, sound effects,
                          emotion, voice design, and scene context.
                          Defaults to all-enabled.

        Returns:
            The ``Book`` produced by the pipeline (with ``character_registry``
            populated and audio written to disk).
        """
        flags = feature_flags or FeatureFlags()

        logger.info(
            "test_workflow_started",
            passage=passage.name,
            book_title=passage.book_title,
            chapter_number=passage.chapter_number,
        )

        # ── Step 1: Build Book from embedded passage ─────────────────────
        sections = [Section(text=para) for para in passage.sections]
        chapter = Chapter(
            number=passage.chapter_number,
            title=passage.chapter_title,
            sections=sections,
        )
        metadata = BookMetadata(
            title=passage.book_title,
            author=passage.author,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )
        book = Book(
            metadata=metadata,
            content=BookContent(chapters=[chapter]),
        )

        # ── Step 2: Inject synthetic book_title + chapter_announcement ────
        formatter = AnnouncementFormatter(self._ai_provider)
        AIProjectGutenbergWorkflow._inject_synthetic_sections(
            [chapter], book.metadata, formatter
        )

        # ── Step 3: AI segmentation ──────────────────────────────────────
        prompt_builder = PromptBuilder(
            book_title=passage.book_title,
            book_author=passage.author,
            feature_flags=flags,
        )
        section_parser = AISectionParser(self._ai_provider, prompt_builder=prompt_builder)

        for idx, section in enumerate(chapter.sections):
            if section.segments is not None:
                continue  # Synthetic section — already resolved
            preceding = chapter.sections[:idx]
            section.segments, book.character_registry = section_parser.parse(
                section,
                book.character_registry,
                context_window=preceding,
                scene_registry=book.scene_registry,
            )

        logger.info(
            "test_workflow_segmentation_done",
            character_count=len(book.character_registry.characters),
        )

        # ── Step 4: Voice assignment ─────────────────────────────────────
        voice_assigner = VoiceAssigner(self._voice_entries)
        voice_assignment = voice_assigner.assign(book.character_registry)

        logger.info(
            "test_workflow_voice_assignment_done",
            character_count=len(voice_assignment),
        )

        # ── Step 5: Audio synthesis ──────────────────────────────────────
        book_id = generate_book_id(book.metadata)
        audio_dir = self._books_dir / book_id / "audio"
        audio_orchestrator = AudioOrchestrator(
            provider=self._tts_provider,
            output_dir=audio_dir,
            debug=debug,
            feature_flags=flags,
            ambient_provider=self._ambient_provider,
        )

        for chap in book.content.chapters:
            logger.info(
                "test_workflow_synthesising_chapter",
                chapter_number=chap.number,
                chapter_title=chap.title,
            )
            audio_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chap.number,
                voice_assignment=voice_assignment,
            )

        logger.info(
            "test_workflow_complete",
            passage=passage.name,
            chapters=len(book.content.chapters),
        )
        return book
