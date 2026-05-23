"""Workflow factory: builds fully-wired Workflow instances by CLI name.

All production dependency wiring lives here. Workflow classes themselves
only declare what they need via ``__init__``; the factory decides which
concrete components to inject.
"""
from pathlib import Path
from typing import Callable

from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.audio.ambient.elevenlabs_ambient_provider import ElevenLabsAmbientProvider
from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner
from src.config.config import Config
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader,
)
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.repository.file_book_repository import FileBookRepository

from .ai_workflow import AIProjectGutenbergWorkflow
from .ambient_workflow import AmbientWorkflow
from .mix_workflow import MixWorkflow
from .music_workflow import MusicWorkflow
from .sfx_workflow import SfxWorkflow
from .tts_workflow import TTSWorkflow
from .workflow import Workflow


def _build_ai(books_dir: Path) -> Workflow:
    repository = FileBookRepository(base_dir=str(books_dir))
    book_source = ProjectGutenbergBookSource(
        downloader=ProjectGutenbergHTMLBookDownloader(),
        metadata_parser=StaticProjectGutenbergHTMLMetadataParser(),
        content_parser=StaticProjectGutenbergHTMLContentParser(),
        repository=repository,
    )

    config = Config.from_env()
    ai_provider: AIProvider
    if config.ai_provider == "anthropic":
        from src.ai.anthropic_provider import AnthropicProvider
        ai_provider = AnthropicProvider(config)
    else:
        ai_provider = AWSBedrockProvider(config)

    return AIProjectGutenbergWorkflow(
        book_source=book_source,
        section_parser=AISectionParser(ai_provider),
        repository=repository,
    )


def _build_tts(books_dir: Path) -> Workflow:
    config = Config.from_env()
    tts_provider = FishAudioTTSProvider(
        api_key=config.require_fish_audio_api_key(),
        books_dir=books_dir,
    )
    return TTSWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        tts_provider=tts_provider,
        voice_assigner=VoiceAssigner(tts_provider),
        books_dir=books_dir,
    )


def _build_ambient(books_dir: Path) -> Workflow:
    from elevenlabs.client import ElevenLabs

    config = Config.from_env()
    client = ElevenLabs(api_key=config.elevenlabs_api_key or "")
    return AmbientWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        provider=ElevenLabsAmbientProvider(
            client=client,
            cache_dir=books_dir / "cache" / "ambient",
        ),
        books_dir=books_dir,
    )


def _build_sfx(books_dir: Path) -> Workflow:
    from elevenlabs.client import ElevenLabs

    config = Config.from_env()
    client = ElevenLabs(api_key=config.elevenlabs_api_key or "")
    return SfxWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        provider=ElevenLabsSoundEffectProvider(
            client=client,
            cache_dir=books_dir / "cache" / "sfx",
        ),
        books_dir=books_dir,
    )


def _build_music(books_dir: Path) -> Workflow:
    return MusicWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        books_dir=books_dir,
    )


def _build_mix(books_dir: Path) -> Workflow:
    return MixWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        books_dir=books_dir,
    )


WorkflowBuilder = Callable[[Path], Workflow]

# Registry of workflow builders keyed by CLI name. To add a new workflow,
# register its builder here; create_workflow() stays closed for modification
# (open/closed principle).
_WORKFLOW_BUILDERS: dict[str, WorkflowBuilder] = {
    "ai": _build_ai,
    "tts": _build_tts,
    "ambient": _build_ambient,
    "sfx": _build_sfx,
    "music": _build_music,
    "mix": _build_mix,
}


def create_workflow(workflow_name: str, books_dir: Path = Path("books")) -> Workflow:
    """Create a workflow instance by name.

    Args:
        workflow_name: Name of the workflow to create (ai, tts, ambient, sfx, music, mix).
        books_dir: Base directory for book output (default: books/).

    Returns:
        A fully-wired Workflow instance.

    Raises:
        ValueError: If workflow_name is not registered.
    """
    try:
        builder = _WORKFLOW_BUILDERS[workflow_name]
    except KeyError as exc:
        raise ValueError(f"Unknown workflow: {workflow_name}") from exc
    return builder(books_dir)
