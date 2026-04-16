"""Free listening eval workflow using Microsoft VibeVoice for TTS.

Identical pipeline to ``ListeningEvalWorkflow`` but wired with free,
local-only providers:

- **TTS**: VibeVoice (open-source, local GPU/CPU inference)
- **Ambient**: Silent WAV stubs
- **Sound Effects**: Silent WAV stubs
- **Music**: Silent WAV stubs

Cost: **$0.00** — no external API calls.  Requires ``torch`` and
``vibevoice`` installed locally.

Run as a CLI::

    python -m src.workflows.listening_eval_vibe_voice_workflow --passage dracula_arrival
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
from src.audio.ambient.vibevoice_ambient_provider import VibeVoiceAmbientProvider
from src.audio.audio_orchestrator import AudioOrchestrator
from src.audio.sound_effect.vibevoice_sound_effect_provider import VibeVoiceSoundEffectProvider
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


class ListeningEvalVibeVoiceWorkflow(Workflow):
    """Free listening eval workflow using VibeVoice TTS + silent stubs.

    Same pipeline as ``ListeningEvalWorkflow``:
    1. Use the Book embedded in the GoldenE2EPassage directly.
    2. AI-segment every non-synthetic section via ``AISectionParser``.
    3. Assign voices via ``VoiceAssigner``.
    4. Synthesise audio via ``AudioOrchestrator``.

    The only cost is the AWS Bedrock call for AI segmentation.  TTS and
    all audio generation providers are free.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        voice_entries: list[VoiceEntry],
        tts_provider: TTSProvider,
        sound_effect_provider: SoundEffectProvider,
        ambient_provider: AmbientProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._ai_provider = ai_provider
        self._voice_entries = voice_entries
        self._tts_provider = tts_provider
        self._sound_effect_provider = sound_effect_provider
        self._ambient_provider = ambient_provider
        self._books_dir = books_dir

    @classmethod
    def create(
        cls,
        books_dir: Path = Path("books"),
        device: str = "cpu",
        model_id: str = "microsoft/VibeVoice-Realtime-0.5B",
    ) -> "ListeningEvalVibeVoiceWorkflow":
        """Factory that wires VibeVoice TTS + silent audio providers.

        Requires:
        - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` for Bedrock
        - ``torch`` + ``vibevoice`` Python packages installed

        Does NOT require any TTS / audio API keys.

        Args:
            books_dir: Base output directory.
            device: PyTorch device for VibeVoice (``"cpu"``, ``"cuda"``, ``"mps"``).
            model_id: HuggingFace model ID or local path for VibeVoice.
        """
        from src.config.config import Config

        config = Config.from_env()

        ai_provider: AIProvider = AWSBedrockProvider(config)

        tts_provider = VibeVoiceTTSProvider(
            model_id=model_id,
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

        sound_effect_provider = VibeVoiceSoundEffectProvider()
        ambient_provider = VibeVoiceAmbientProvider()

        return cls(
            ai_provider=ai_provider,
            voice_entries=voice_entries,
            tts_provider=tts_provider,
            sound_effect_provider=sound_effect_provider,
            ambient_provider=ambient_provider,
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
            "vibe_voice_eval_workflow_started",
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
            "vibe_voice_eval_segmentation_done",
            character_count=len(book.character_registry.characters),
        )

        # ── Step 3: Voice assignment ─────────────────────────────────────
        voice_assigner = VoiceAssigner(self._voice_entries)
        voice_assignment = voice_assigner.assign(book.character_registry)

        logger.info(
            "vibe_voice_eval_voice_assignment_done",
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
                "vibe_voice_eval_synthesising_chapter",
                chapter_number=chap.number,
                chapter_title=chap.title,
            )
            audio_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chap.number,
                voice_assignment=voice_assignment,
            )

        logger.info(
            "vibe_voice_eval_workflow_complete",
            passage=passage.name,
            chapters=len(book.content.chapters),
        )
        return book


# ═══════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    """CLI entry point for the free VibeVoice listening eval."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

    from src.config.logging_config import configure
    configure()

    parser = argparse.ArgumentParser(
        description=(
            "Run the full audiobook pipeline on a golden passage using "
            "VibeVoice (free, local TTS). Ambient/SFX/music use silent stubs."
        ),
    )
    parser.add_argument("--passage", metavar="NAME", required=True,
                        help="Named golden passage (e.g. 'dracula_arrival').")
    parser.add_argument("--output-dir", metavar="DIR", default="evals_output",
                        help="Base directory for output (default: evals_output).")
    parser.add_argument("--device", metavar="DEVICE", default="cpu",
                        help="PyTorch device for VibeVoice (cpu, cuda, mps). Default: cpu.")
    parser.add_argument("--model-id", metavar="MODEL", default="microsoft/VibeVoice-Realtime-0.5B",
                        help="HuggingFace model ID or local path. Default: microsoft/VibeVoice-Realtime-0.5B.")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="Keep individual segment audio files.")
    args = parser.parse_args()

    passage = _resolve_passage(args.passage)

    now = datetime.utcnow()
    output_dir = Path(args.output_dir) / f"e2e-vibevoice-{now.strftime('%Y-%m-%d-%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\nRunning FREE E2E listening eval (VibeVoice TTS + silent stubs)...")
    first_chapter = passage.book.content.chapters[0]
    print(f"Passage: {passage.name} ({passage.book.metadata.title}, Chapter {first_chapter.number})")
    print(f"Device:  {args.device}")
    print(f"Model:   {args.model_id}")
    print(f"Output:  {output_dir}/")
    print("Cost:    $0.00 (local inference only)\n")

    feature_flags = FeatureFlags(
        ambient_enabled=True,
        sound_effects_enabled=True,
        emotion_enabled=True,
        voice_design_enabled=True,
        scene_context_enabled=True,
        chapter_announcer_enabled=True,
    )

    books_dir = output_dir / "books"
    workflow = ListeningEvalVibeVoiceWorkflow.create(
        books_dir=books_dir,
        device=args.device,
        model_id=args.model_id,
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
    print("E2E LISTENING EVAL (VibeVoice) \u2014 Generated audio ready for review")
    print(f"{border}\n")
    print(f"Output: {output_path}")
    print(f"Duration: {minutes}:{secs:02d}\n")
    print("Listen for the following features:\n")
    for feat in _CHECKLIST_FEATURES:
        print(f"[ ] {feat}")
    print("\nCost: $0.00 (VibeVoice local TTS + silent ambient/SFX/music stubs)")
    print("Note: Ambient, SFX, and music are silent stubs — only TTS quality is evaluated.\n")


if __name__ == "__main__":
    main()
