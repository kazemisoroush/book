"""Free listening eval workflow using AudioCraft for ambient/SFX/music and VibeVoice for TTS.

Identical pipeline to ``ListeningEvalWorkflow`` but wired with free,
local-only providers:

- **TTS**: VibeVoice (open-source, local GPU/CPU inference)
- **Ambient**: AudioGen (Meta AudioCraft, local inference)
- **Sound Effects**: AudioGen (Meta AudioCraft, local inference)
- **Music**: MusicGen (Meta AudioCraft, local inference)

Cost: **$0.00** — no external API calls.  Requires ``torch``, ``torchaudio``,
``audiocraft``, and ``vibevoice`` installed locally.

Run as a CLI::

    python -m src.workflows.listening_eval_free_workflow --passage dracula_arrival
"""

import argparse
import shutil
import sys
from datetime import datetime
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
from src.audio.sound_effect.audiogen_sound_effect_provider import AudioGenSoundEffectProvider
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.vibevoice_tts_provider import VibeVoiceTTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.config.feature_flags import FeatureFlags
from src.domain.models import Book
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.prompt_builder import PromptBuilder
from src.repository.book_id import generate_book_id
from src.workflows.listening_eval_workflow import (
    GoldenE2EPassage,
    _CHECKLIST_FEATURES,
    _get_audio_duration_seconds,
    _resolve_passage,
)
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
        voice_entries: list[VoiceEntry],
        tts_provider: TTSProvider,
        sound_effect_provider: SoundEffectProvider,
        ambient_provider: AmbientProvider,
        music_provider: MusicProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._ai_provider = ai_provider
        self._voice_entries = voice_entries
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

        voices = tts_provider.get_voices()
        voice_entries = [
            VoiceEntry(
                voice_id=v["voice_id"],
                name=v["name"],
                labels=v["labels"],
            )
            for v in voices
        ]

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
            voice_entries=voice_entries,
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
        reparse: bool = False,
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
        voice_assigner = VoiceAssigner(self._voice_entries)
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


# ═══════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    """CLI entry point for the free listening eval (AudioCraft + VibeVoice)."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

    from src.config.logging_config import configure
    configure()

    parser = argparse.ArgumentParser(
        description=(
            "Run the full audiobook pipeline on a golden passage using "
            "VibeVoice TTS + AudioCraft ambient/SFX/music. Free, local inference."
        ),
    )
    parser.add_argument("--passage", metavar="NAME", required=True,
                        help="Named golden passage (e.g. 'dracula_arrival').")
    parser.add_argument("--output-dir", metavar="DIR", default="evals_output",
                        help="Base directory for output (default: evals_output).")
    parser.add_argument("--device", metavar="DEVICE", default="cpu",
                        help="PyTorch device for all models (cpu, cuda, mps). Default: cpu.")
    parser.add_argument("--tts-model", metavar="MODEL", default="microsoft/VibeVoice-Realtime-0.5B",
                        help="HuggingFace model ID for VibeVoice TTS. Default: microsoft/VibeVoice-Realtime-0.5B.")
    parser.add_argument("--audiogen-model", metavar="MODEL", default="facebook/audiogen-medium",
                        help="HuggingFace model ID for AudioGen (ambient + SFX). Default: facebook/audiogen-medium.")
    parser.add_argument("--musicgen-model", metavar="MODEL", default="facebook/musicgen-small",
                        help="HuggingFace model ID for MusicGen (music). Default: facebook/musicgen-small.")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="Keep individual segment audio files.")
    args = parser.parse_args()

    passage = _resolve_passage(args.passage)

    now = datetime.utcnow()
    output_dir = Path(args.output_dir) / f"e2e-free-{now.strftime('%Y-%m-%d-%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\nRunning FREE E2E listening eval (VibeVoice TTS + AudioCraft ambient/SFX/music)...")
    first_chapter = passage.book.content.chapters[0]
    print(f"Passage:       {passage.name} ({passage.book.metadata.title}, Chapter {first_chapter.number})")
    print(f"Device:        {args.device}")
    print(f"TTS model:     {args.tts_model}")
    print(f"AudioGen:      {args.audiogen_model}")
    print(f"MusicGen:      {args.musicgen_model}")
    print(f"Output:        {output_dir}/")
    print("Cost:          $0.00 (local inference only)\n")

    feature_flags = FeatureFlags(
        ambient_enabled=True,
        sound_effects_enabled=True,
        emotion_enabled=True,
        voice_design_enabled=True,
        scene_context_enabled=True,
        chapter_announcer_enabled=True,
    )

    books_dir = output_dir / "books"
    workflow = ListeningEvalFreeWorkflow.create(
        books_dir=books_dir,
        device=args.device,
        tts_model=args.tts_model,
        audiogen_model=args.audiogen_model,
        musicgen_model=args.musicgen_model,
    )
    book = workflow.run(passage=passage, debug=args.debug, feature_flags=feature_flags)

    # Locate and copy the generated chapter audio
    chapter = book.content.chapters[0]
    book_id = generate_book_id(book.metadata)
    audio_dir = books_dir / book_id / "audio"
    chapter_mp3 = audio_dir / f"chapter_{chapter.number:02d}" / "chapter.mp3"

    if not chapter_mp3.exists():
        found = list(audio_dir.glob("**/chapter.mp3"))
        chapter_mp3 = found[0] if found else None  # type: ignore[assignment]

    if chapter_mp3 is None or not chapter_mp3.exists():
        print(f"\nWARNING: Could not locate chapter audio in {audio_dir}/", file=sys.stderr)
        output_path = audio_dir / "chapter.mp3"
        duration = 0
    else:
        dest = output_dir / "chapter.mp3"
        shutil.copy2(chapter_mp3, dest)
        output_path = dest
        duration = _get_audio_duration_seconds(dest)

    # Print listening checklist
    minutes, secs = divmod(duration, 60)
    border = "\u2550" * 62
    print(f"\n{border}")
    print("E2E LISTENING EVAL (Free) \u2014 Generated audio ready for review")
    print(f"{border}\n")
    print(f"Output: {output_path}")
    print(f"Duration: {minutes}:{secs:02d}\n")
    print("Listen for the following features:\n")
    for feat in _CHECKLIST_FEATURES:
        print(f"[ ] {feat}")
    print("\nCost: $0.00 (VibeVoice TTS + AudioCraft ambient/SFX/music, local inference)\n")


if __name__ == "__main__":
    main()
