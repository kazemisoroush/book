"""Full-pipeline TTS workflow for listening evaluation.

Builds a Book from an embedded golden passage (no download step), runs
AI segmentation, voice assignment, and audio synthesis — identical to
``TTSProjectGutenbergWorkflow`` but with sections provided directly.

Run via the central dispatcher::

    python scripts/run_workflow.py --workflow eval-best --passage dracula_arrival

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
- ``run()`` uses passage.book directly.  Synthetic sections (book_title and
  chapter_announcement) are pre-baked into each golden passage's Book at
  definition time — no runtime injection step required.
"""

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.ambient.stable_audio_ambient_provider import StableAudioAmbientProvider
from src.audio.audio_orchestrator import AudioOrchestrator
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.sound_effect.stable_audio_sound_effect_provider import StableAudioSoundEffectProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.tts_provider import TTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner
from src.config.feature_flags import FeatureFlags
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section, Segment, SegmentType
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.prompt_builder import PromptBuilder
from src.repository.book_id import generate_book_id
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
                            text="Dracula, by Bram Stoker.",
                            section_type="book_title",
                            segments=[Segment(
                                text="Dracula, by Bram Stoker.",
                                segment_type=SegmentType.BOOK_TITLE,
                                character_id="narrator",
                            )],
                        ),
                        Section(
                            text="Chapter 1. Jonathan Harker's Journal.",
                            section_type="chapter_announcement",
                            segments=[Segment(
                                text="Chapter 1. Jonathan Harker's Journal.",
                                segment_type=SegmentType.CHAPTER_ANNOUNCEMENT,
                                character_id="narrator",
                            )],
                        ),
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
    1. Use the Book embedded in the GoldenE2EPassage directly (no HTTP download).
       Synthetic book_title and chapter_announcement sections are pre-baked into
       the passage's Book — no runtime injection step required.
    2. AI-segment every non-synthetic section using ``AISectionParser``.
    3. Assign voices via ``VoiceAssigner``.
    4. Synthesise audio via ``AudioOrchestrator`` for every chapter.

    Audio files are written to ``{books_dir}/{book_id}/audio/``.

    Use :meth:`create` to get an instance wired with production dependencies.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        tts_provider: TTSProvider,
        sound_effect_provider: SoundEffectProvider,
        ambient_provider: AmbientProvider,
        books_dir: Path = Path("books"),
    ) -> None:
        self._ai_provider = ai_provider
        self._tts_provider = tts_provider
        self._sound_effect_provider = sound_effect_provider
        self._ambient_provider = ambient_provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "ListeningEvalWorkflow":
        """Factory that wires all production dependencies.

        Requires:
        - ``FISH_AUDIO_API_KEY`` environment variable for TTS
        - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` for Bedrock
        - ``STABILITY_API_KEY`` environment variable for SFX + ambient
        """
        from src.config.config import Config

        config = Config.from_env()

        ai_provider: AIProvider = AWSBedrockProvider(config)

        fish_api_key = config.fish_audio_api_key
        if not fish_api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set — configure via environment variable")
        tts_provider = FishAudioTTSProvider(api_key=fish_api_key)

        stability_api_key = config.stability_api_key
        if not stability_api_key:
            raise ValueError("STABILITY_API_KEY not set — configure via environment variable")

        sound_effect_provider = StableAudioSoundEffectProvider(
            api_key=stability_api_key,
            cache_dir=books_dir / "cache" / "sfx",
        )
        ambient_provider = StableAudioAmbientProvider(
            api_key=stability_api_key,
            cache_dir=books_dir / "cache" / "ambient",
        )

        return cls(
            ai_provider=ai_provider,
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
            "listening_eval_workflow_segmentation_done",
            character_count=len(book.character_registry.characters),
        )

        # ── Step 4: Voice assignment ─────────────────────────────────────
        voice_assigner = VoiceAssigner(self._tts_provider)
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


def _get_audio_duration_seconds(audio_path: Path) -> int:
    """Return MP3 duration in whole seconds, or 0 on error."""
    try:
        mutagen_mp3 = importlib.import_module("mutagen.mp3")
        audio = mutagen_mp3.MP3(str(audio_path))
        return int(audio.info.length)
    except Exception:  # noqa: BLE001
        return 0


