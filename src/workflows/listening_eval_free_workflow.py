"""Free listening eval workflow using AudioCraft for ambient/SFX/music and VibeVoice for TTS.

Identical pipeline to ``ListeningEvalWorkflow`` but wired with free,
local-only providers:

- **TTS**: VibeVoice (open-source, local GPU/CPU inference)
- **Ambient**: AudioGen (Meta AudioCraft, local inference)
- **Sound Effects**: AudioGen (Meta AudioCraft, local inference)
- **Music**: MusicGen (Meta AudioCraft, local inference)

Cost: **$0.00** — no external API calls.  Requires ``torch``, ``torchaudio``,
``audiocraft``, and ``vibevoice`` installed locally.

Run via the central dispatcher::

    python scripts/run_workflow.py --workflow eval-free --passage dracula_arrival --device cuda
"""

from pathlib import Path
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.ambient.audiogen_ambient_provider import AudioGenAmbientProvider
from src.audio.audio_orchestrator import AudioOrchestrator
from src.audio.music.music_provider import MusicProvider
from src.audio.music.musicgen_music_provider import MusicGenMusicProvider
from src.audio.sound_effect.audiogen_sound_effect_provider import (
    AudioGenSoundEffectProvider,
)
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.vibevoice_tts_provider import VibeVoiceTTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner
from src.config.feature_flags import FeatureFlags
from src.domain.models import Book
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.prompt_builder import PromptBuilder
from src.repository.book_id import generate_book_id
from src.workflows.listening_eval_workflow import GoldenE2EPassage
from src.workflows.workflow import Workflow

logger = structlog.get_logger(__name__)


class ListeningEvalFreeWorkflow(Workflow):
    """Free listening eval workflow using VibeVoice TTS + AudioCraft audio providers.

    Same pipeline as ``ListeningEvalWorkflow``:
    1. Use the Book embedded in the GoldenE2EPassage directly.
    2. AI-segment every non-synthetic section via ``AISectionParser``.
    3. Assign voices via ``VoiceAssigner``.
    4. Synthesise audio via ``AudioOrchestrator``.

    The only cost is the AWS Bedrock call for AI segmentation.  TTS and
    all audio generation providers are free (local inference).
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        tts_provider: TTSProvider,
        sound_effect_provider: SoundEffectProvider,
        ambient_provider: AmbientProvider,
        music_provider: MusicProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._ai_provider = ai_provider
        self._tts_provider = tts_provider
        self._sound_effect_provider = sound_effect_provider
        self._ambient_provider = ambient_provider
        self._music_provider = music_provider
        self._books_dir = books_dir

    @classmethod
    def create(
        cls,
        books_dir: Path = Path("books"),
        device: str = "cpu",
        tts_model: str = "microsoft/VibeVoice-Realtime-0.5B",
        audiogen_model: str = "facebook/audiogen-medium",
        musicgen_model: str = "facebook/musicgen-small",
    ) -> "ListeningEvalFreeWorkflow":
        """Factory that wires VibeVoice TTS + AudioCraft audio providers.

        Requires:
        - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` for Bedrock
        - ``torch`` + ``torchaudio`` + ``audiocraft`` + ``vibevoice`` Python packages installed

        Does NOT require any TTS / audio API keys.

        Args:
            books_dir: Base output directory.
            device: PyTorch device for all models (``"cpu"``, ``"cuda"``, ``"mps"``).
            tts_model: HuggingFace model ID or local path for VibeVoice TTS.
            audiogen_model: HuggingFace model ID for AudioGen (ambient + SFX).
            musicgen_model: HuggingFace model ID for MusicGen (music).
        """
        from src.config.config import Config

        config = Config.from_env()

        ai_provider: AIProvider = AWSBedrockProvider(config)

        tts_provider = VibeVoiceTTSProvider(
            model_id=tts_model,
            device=device,
        )

        sound_effect_provider = AudioGenSoundEffectProvider(
            model_id=audiogen_model,
            device=device,
        )
        ambient_provider = AudioGenAmbientProvider(
            model_id=audiogen_model,
            device=device,
        )
        music_provider = MusicGenMusicProvider(
            model_id=musicgen_model,
            device=device,
        )

        return cls(
            ai_provider=ai_provider,
            tts_provider=tts_provider,
            sound_effect_provider=sound_effect_provider,
            ambient_provider=ambient_provider,
            music_provider=music_provider,
            books_dir=books_dir,
        )

    def run(  # type: ignore[override]
        self,
        passage: GoldenE2EPassage,
        debug: bool = False,
        feature_flags: Optional[FeatureFlags] = None,
        url: str = "",
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Run the full pipeline for a golden passage and synthesise audio.

        Args:
            passage: Golden passage whose sections drive the pipeline.
            debug: Keep individual segment audio files alongside the
                   stitched chapter audio.
            feature_flags: Feature toggles.  Defaults to all-enabled.

        Returns:
            The ``Book`` with audio written to disk.
        """
        flags = feature_flags or FeatureFlags()

        logger.info(
            "free_eval_workflow_started",
            passage=passage.name,
            book_title=passage.book.metadata.title,
            chapter_count=len(passage.book.content.chapters),
        )

        # ── Step 1: Use the Book embedded in the passage directly ────────
        book = passage.book

        # ── Step 2: AI segmentation ──────────────────────────────────────
        prompt_builder = PromptBuilder(
            book_title=book.metadata.title,
            book_author=book.metadata.author,
            feature_flags=flags,
        )
        section_parser = AISectionParser(self._ai_provider, prompt_builder=prompt_builder)

        for chap in book.content.chapters:
            for idx, section in enumerate(chap.sections):
                if section.segments is not None:
                    continue  # Synthetic section — already resolved
                preceding = chap.sections[:idx]
                section.segments, book.character_registry = section_parser.parse(
                    section,
                    book.character_registry,
                    context_window=preceding,
                    scene_registry=book.scene_registry,
                )

        logger.info(
            "free_eval_segmentation_done",
            character_count=len(book.character_registry.characters),
        )

        # ── Step 3: Voice assignment ─────────────────────────────────────
        voice_assigner = VoiceAssigner(self._tts_provider)
        voice_assignment = voice_assigner.assign(book.character_registry)

        logger.info(
            "free_eval_voice_assignment_done",
            character_count=len(voice_assignment),
        )

        # ── Step 4: Audio synthesis ──────────────────────────────────────
        book_id = generate_book_id(book.metadata)
        audio_dir = self._books_dir / book_id / "audio"
        audio_orchestrator = AudioOrchestrator(
            provider=self._tts_provider,
            output_dir=audio_dir,
            debug=debug,
            feature_flags=flags,
            sound_effect_provider=self._sound_effect_provider,
            ambient_provider=self._ambient_provider,
        )

        for chap in book.content.chapters:
            logger.info(
                "free_eval_synthesising_chapter",
                chapter_number=chap.number,
                chapter_title=chap.title,
            )
            audio_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chap.number,
                voice_assignment=voice_assignment,
            )

        logger.info(
            "free_eval_workflow_complete",
            passage=passage.name,
            chapters=len(book.content.chapters),
        )
        return book


