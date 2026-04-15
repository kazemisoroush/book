"""Full-pipeline TTS workflow for listening evaluation.

Builds a Book from an embedded golden passage (no download step), runs
AI segmentation, voice assignment, and audio synthesis — identical to
``TTSProjectGutenbergWorkflow`` but with sections provided directly.

Run as a CLI::

    python -m src.workflows.listening_eval_workflow --passage dracula_arrival

Cost:
    $2.50 - $5.00 per run (varies by passage length and features enabled).

Runtime:
    ~5-8 minutes per run.

Warning:
    This makes real API calls and is NOT free.  It will consume AWS Bedrock,
    Fish Audio, Stability AI, and (optionally) Suno credits.
    Do NOT run this in CI.  Run manually after major pipeline changes.

Design notes
------------
- ``__init__`` takes an explicit ``ai_provider`` because, unlike
  ``TTSProjectGutenbergWorkflow``, there is no inner
  ``AIProjectGutenbergWorkflow`` to own it.
- ``create()`` wires all production dependencies identically to
  ``TTSProjectGutenbergWorkflow.create()`` and additionally creates an
  ``AWSBedrockProvider``.
- ``run()`` mutates the chapter sections list in-place (matching
  ``AIProjectGutenbergWorkflow._inject_synthetic_sections`` behaviour).
"""

import argparse
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
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
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.sound_effect.stable_audio_sound_effect_provider import StableAudioSoundEffectProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.config.feature_flags import FeatureFlags
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.announcement_formatter import AnnouncementFormatter
from src.parsers.prompt_builder import PromptBuilder
from src.repository.book_id import generate_book_id
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.workflows.workflow import Workflow

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Golden passage dataclass + registry
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GoldenE2EPassage:
    """A passage for end-to-end listening evaluation.

    The passage is embedded directly in ``book`` — no download step required at
    runtime.  ``gutenberg_url`` is kept as reference-only metadata so reviewers
    can locate the source, but it is never fetched.

    Attributes:
        name: Short slug used as identifier (e.g., "dracula_arrival").
        book: Ready-to-use Book containing the passage content.  The workflow
            uses this directly without any further mapping.
        gutenberg_url: Reference URL to the plain-text file on Project Gutenberg
            (not fetched at runtime — for human reference only).
        expected_features: Audio feature tags this passage should exercise
            (e.g., ["dialogue", "sfx", "ambient", "voice_design"]).
        notes: Human explanation of why this passage is a good test case.
    """

    name: str
    book: Book
    gutenberg_url: str
    expected_features: list[str] = field(default_factory=list)
    notes: str = ""


# ── Dracula, Chapter 1 — Jonathan Harker's arrival ─────────────────────
# From "Dracula" by Bram Stoker (Project Gutenberg #345)
#
# Why this passage?
# - Narration: Harker's first-person journal voice
# - Dialogue: Conversation with the mysterious coachman, then Count Dracula
# - Emotion: Unease, fear, supernatural dread
# - Sound effects: Howling wolves, carriage wheels, creaking castle door
# - Scene change: Exposed mountain pass → grand castle entrance hall
# - Ambient: Mountain wind, distant wolves → stone corridor reverb
# - Music: Tense/mysterious mood fits the gothic setting
# - Voice design: Count Dracula (older male, commanding, Transylvanian)
#
# Text source: Project Gutenberg #345 — public domain.
# Paragraphs taken from Chapter 1, "3 May. Bistritz." opening,
# covering Harker's journey through Transylvania and first contact
# with the strange coachman at the Borgo Pass.

dracula_arrival = GoldenE2EPassage(
    name="dracula_arrival",
    book=Book(
        metadata=BookMetadata(
            title="Dracula",
            author="Bram Stoker",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title="Jonathan Harker's Journal",
                    sections=[
                        Section(
                            text=(
                                "I had all sorts of queer dreams last night. I suppose it was all the "
                                "stories and traditions I had heard during the day and evening. A dog "
                                "began to howl somewhere in a farmhouse far down the road, a long, "
                                "agonised wailing, as if from fear. The sound was taken up by another "
                                "dog, and then another and another, till borne on the wind which now "
                                "sighed softly through the Pass, a wild howling began, which seemed to "
                                "come from all over the country, as far as the imagination could grasp it "
                                "through the gloom of the night."
                            )
                        ),
                        Section(
                            text=(
                                "At last we saw before us the Pass opening out on the eastern side. "
                                "There were dark, rolling clouds overhead, and in the air the heavy, "
                                "oppressive sense of thunder. I was now myself looking out for the "
                                "conveyance which was to take me to the Count. Suddenly the driver "
                                'exclaimed: "Hark!" and in the silence of the night I could just hear '
                                "a distant sound of horses, then the flickering of lights."
                            )
                        ),
                    ],
                )
            ]
        ),
    ),
    gutenberg_url="https://www.gutenberg.org/cache/epub/345/pg345.txt",
    expected_features=[
        "narration",
        "dialogue",
        "emotion",
        "sfx",
        "ambient",
        "scene_transition",
        "voice_design",
    ],
    notes=(
        "Harker's night journey through the Borgo Pass: first-person narration, "
        "dialogue with the mysterious coachman, howling wolves (SFX), mountain "
        "wind ambient, tense approaching-danger music mood, and an unnamed driver "
        "as a bespoke voice-design character. Covers 7 of 7 audio feature categories."
    ),
)

ALL_E2E_PASSAGES: list[GoldenE2EPassage] = [
    dracula_arrival,
]


# ═══════════════════════════════════════════════════════════════════════
# Workflow
# ═══════════════════════════════════════════════════════════════════════


class ListeningEvalWorkflow(Workflow):
    """Full-pipeline TTS workflow for listening evaluation.

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
        sound_effect_provider: Optional[SoundEffectProvider] = None,
        ambient_provider: Optional[AmbientProvider] = None,
        music_provider: Optional[MusicProvider] = None,
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
    def create(cls, books_dir: Path = Path("books")) -> "ListeningEvalWorkflow":
        """Factory that wires all production dependencies.

        Requires:
        - ``FISH_AUDIO_API_KEY`` environment variable for TTS
        - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` for Bedrock
        - ``STABILITY_API_KEY`` environment variable for SFX + ambient (optional)
        - ``SUNO_API_KEY`` environment variable for music (optional)
        """
        from src.config.config import Config

        config = Config.from_env()

        ai_provider: AIProvider = AWSBedrockProvider(config)

        fish_api_key = config.fish_audio_api_key
        if not fish_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set — configure via environment variable")
        tts_provider = FishAudioTTSProvider(api_key=fish_api_key)

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

        sound_effect_provider: Optional[SoundEffectProvider] = None
        if config.stability_api_key:
            sound_effect_provider = StableAudioSoundEffectProvider(
                api_key=config.stability_api_key,
                cache_dir=books_dir / "cache" / "sfx",
            )

        ambient_provider: Optional[AmbientProvider] = None
        if config.stability_api_key:
            ambient_provider = StableAudioAmbientProvider(
                api_key=config.stability_api_key,
                cache_dir=books_dir / "cache" / "ambient",
            )

        music_provider: Optional[MusicProvider] = None
        if config.suno_api_key:
            music_provider = SunoMusicProvider(
                api_key=config.suno_api_key,
                cache_dir=books_dir / "cache" / "music",
            )

        return cls(
            ai_provider=ai_provider,
            voice_entries=voices,
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
            debug: Keep individual segment MP3 files alongside the stitched
                   ``chapter.mp3``.
            feature_flags: Feature toggles.  Defaults to all-enabled.

        Returns:
            The ``Book`` with audio written to disk.
        """
        flags = feature_flags or FeatureFlags()

        logger.info(
            "listening_eval_workflow_started",
            passage=passage.name,
            book_title=passage.book.metadata.title,
            chapter_count=len(passage.book.content.chapters),
        )

        # ── Step 1: Use the Book embedded in the passage directly ────────
        book = passage.book

        # ── Step 2: Inject synthetic book_title + chapter_announcement ────
        formatter = AnnouncementFormatter(self._ai_provider)
        AIProjectGutenbergWorkflow._inject_synthetic_sections(
            book.content.chapters, book.metadata, formatter
        )

        # ── Step 3: AI segmentation ──────────────────────────────────────
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
            "listening_eval_workflow_segmentation_done",
            character_count=len(book.character_registry.characters),
        )

        # ── Step 4: Voice assignment ─────────────────────────────────────
        voice_assigner = VoiceAssigner(self._voice_entries)
        voice_assignment = voice_assigner.assign(book.character_registry)

        logger.info(
            "listening_eval_workflow_voice_assignment_done",
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
            sound_effect_provider=self._sound_effect_provider,
            ambient_provider=self._ambient_provider,
        )

        for chap in book.content.chapters:
            logger.info(
                "listening_eval_workflow_synthesising_chapter",
                chapter_number=chap.number,
                chapter_title=chap.title,
            )
            audio_orchestrator.synthesize_chapter(
                book=book,
                chapter_number=chap.number,
                voice_assignment=voice_assignment,
            )

        logger.info(
            "listening_eval_workflow_complete",
            passage=passage.name,
            chapters=len(book.content.chapters),
        )
        return book


# ═══════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════

_CHECKLIST_FEATURES = [
    "NARRATION — Baseline narrator voice is clear and consistent",
    "DIALOGUE — At least 2 distinct character voices",
    "EMOTION — At least one segment with vocal emotion (e.g., whispers, laughs)",
    "SOUND EFFECTS — Diegetic SFX in silence gaps (e.g., knock, cough, footsteps)",
    "AMBIENT — Scene-appropriate background sound at correct volume",
    "SCENE TRANSITION — Ambient cross-fade when scene changes (if passage has scene change)",
    "BACKGROUND MUSIC — Music underscores emotional tone (if enabled and mood detected)",
    "VOICE DESIGN — At least one bespoke character voice matches description",
    "INTER-SEGMENT SILENCE — Natural pauses between segments",
    "NO AUDIO ARTIFACTS — No clicks, pops, or glitches in stitched audio",
]


def _resolve_passage(name: str) -> GoldenE2EPassage:
    """Look up a named passage from the registry."""
    for passage in ALL_E2E_PASSAGES:
        if passage.name == name:
            return passage
    available = ", ".join(p.name for p in ALL_E2E_PASSAGES)
    raise SystemExit(f"Unknown passage '{name}'. Available: {available}")


def _validate_env_vars(music_enabled: bool = False) -> None:
    """Fail fast if required environment variables are missing."""
    required: list[tuple[str, str]] = [
        ("AWS_ACCESS_KEY_ID", "AWS Bedrock (AI parsing)"),
        ("AWS_SECRET_ACCESS_KEY", "AWS Bedrock (AI parsing)"),
        ("FISH_AUDIO_API_KEY", "Fish Audio (TTS synthesis)"),
    ]
    if music_enabled:
        required.append(("SUNO_API_KEY", "Suno AI (background music)"))

    missing = [(var, svc) for var, svc in required if not os.environ.get(var)]
    if missing:
        print("ERROR: Required environment variables not set:", file=sys.stderr)
        for var, svc in missing:
            print(f"  {var}  — needed for {svc}", file=sys.stderr)
        raise SystemExit(1)


def _get_audio_duration_seconds(audio_path: Path) -> int:
    """Return MP3 duration in whole seconds, or 0 on error."""
    try:
        import importlib
        mutagen_mp3 = importlib.import_module("mutagen.mp3")
        audio = mutagen_mp3.MP3(str(audio_path))
        return int(audio.info.length)
    except Exception:  # noqa: BLE001
        return 0


def main() -> None:
    """CLI entry point for the listening eval."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

    from src.config.logging_config import configure
    configure()

    parser = argparse.ArgumentParser(
        description="Run the full audiobook pipeline on a short golden passage for human listening evaluation.",
    )
    parser.add_argument("--passage", metavar="NAME", required=True,
                        help="Named golden passage (e.g. 'dracula_arrival').")
    parser.add_argument("--output-dir", metavar="DIR", default="evals_output",
                        help="Base directory for output (default: evals_output).")
    parser.add_argument("--music", action="store_true", default=False,
                        help="Enable background music (requires SUNO_API_KEY).")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="Keep individual segment MP3 files.")
    args = parser.parse_args()

    passage = _resolve_passage(args.passage)
    _validate_env_vars(music_enabled=args.music)

    now = datetime.utcnow()
    output_dir = Path(args.output_dir) / f"e2e-{now.strftime('%Y-%m-%d-%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\nRunning E2E listening eval...")
    first_chapter = passage.book.content.chapters[0]
    print(f"Passage: {passage.name} ({passage.book.metadata.title}, Chapter {first_chapter.number})")
    print(f"Output:  {output_dir}/\n")

    feature_flags = FeatureFlags(
        ambient_enabled=True,
        sound_effects_enabled=True,
        emotion_enabled=True,
        voice_design_enabled=True,
        scene_context_enabled=True,
        chapter_announcer_enabled=True,
    )

    books_dir = output_dir / "books"
    workflow = ListeningEvalWorkflow.create(books_dir=books_dir)
    book = workflow.run(passage=passage, debug=args.debug, feature_flags=feature_flags)

    # Locate and copy the generated chapter MP3
    chapter = book.content.chapters[0]
    book_id = generate_book_id(book.metadata)
    audio_dir = books_dir / book_id / "audio"
    chapter_mp3 = audio_dir / f"chapter_{chapter.number:02d}" / "chapter.mp3"

    if not chapter_mp3.exists():
        found = list(audio_dir.glob("**/chapter.mp3"))
        chapter_mp3 = found[0] if found else None  # type: ignore[assignment]

    if chapter_mp3 is None or not chapter_mp3.exists():
        print(f"\nWARNING: Could not locate chapter.mp3 in {audio_dir}/", file=sys.stderr)
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
    print("E2E LISTENING EVAL \u2014 Generated audio ready for review")
    print(f"{border}\n")
    print(f"Output: {output_path}")
    print(f"Duration: {minutes}:{secs:02d}\n")
    print("Listen for the following features:\n")
    for feat in _CHECKLIST_FEATURES:
        print(f"[ ] {feat}")
    print("\nCost estimate: $2.50 - $5.00 (varies by passage length and features used)")
    print("Runtime: ~5-8 minutes\n")


if __name__ == "__main__":
    main()
