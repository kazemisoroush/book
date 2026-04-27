"""Custom promptfoo provider for the section-parser AI pipeline.

This provider calls the real PromptBuilder + AWSBedrockProvider stack,
exactly as the application does, so promptfoo evals test the actual
prompt+model combination.

The output matches the ``book.json`` schema: each section has ``text``,
``beats`` (with ``beat_type``, ``character_id``, ``emotion``, etc.),
and ``section_type``.  Top-level keys ``character_registry`` and
``scene_registry`` mirror ``Book.to_dict()``.

promptfoo invokes ``call_api(prompt, options, context)`` and expects
a dict back with ``{"output": <JSON object>}``.
"""
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so ``src.*`` imports work.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.ai.aws_bedrock_provider import AWSBedrockProvider  # noqa: E402
from src.config.config import Config  # noqa: E402
from src.domain.models import (  # noqa: E402
    CharacterRegistry,
    MoodRegistry,
    SceneRegistry,
    Section,
)
from src.parsers.ai_section_parser import AISectionParser  # noqa: E402
from src.parsers.prompt_builder import PromptBuilder  # noqa: E402


def call_api(
    prompt: str,
    options: dict,  # type: ignore[type-arg]
    context: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Run a passage through the section-parser pipeline.

    ``context["vars"]`` must contain:
      - ``text``: the passage text to parse
      - ``book_title``: book title for prompt context
      - ``book_author``: book author for prompt context
    """
    vars_ = context.get("vars", {})
    text = vars_["text"]
    book_title = vars_.get("book_title", "")
    book_author = vars_.get("book_author", "")
    mood_registry_data = vars_.get("mood_registry") or []
    current_open_mood_id = vars_.get("current_open_mood_id")

    config = Config.from_env()
    ai_provider = AWSBedrockProvider(config)

    prompt_builder = PromptBuilder(
        book_title=book_title,
        book_author=book_author,
    )
    parser = AISectionParser(ai_provider, prompt_builder=prompt_builder)

    registry = CharacterRegistry.with_default_narrator()
    scene_registry = SceneRegistry()
    mood_registry = (
        MoodRegistry.from_dict(mood_registry_data)
        if mood_registry_data
        else MoodRegistry()
    )
    section = Section(text=text)

    beats, registry = parser.parse(
        section, registry, scene_registry=scene_registry,
        mood_registry=mood_registry,
        current_open_mood_id=current_open_mood_id,
    )

    # Return in book.json format
    output = {
        "sections": [
            {
                "text": text,
                "beats": [
                    {
                        "text": s.text,
                        "beat_type": s.beat_type.value,
                        "character_id": s.character_id,
                        "scene_id": s.scene_id,
                        "emotion": s.emotion,
                        "voice_stability": s.voice_stability,
                        "voice_style": s.voice_style,
                        "voice_speed": s.voice_speed,
                        "sound_effect_detail": s.sound_effect_detail,
                    }
                    for s in beats
                ],
                "section_type": None,
            }
        ],
        "character_registry": [
            c.to_dict() for c in registry.characters
        ],
        "scene_registry": scene_registry.to_dict(),
    }

    # Surface the decoded mood action so mood-change evals can assert on it.
    action = parser.last_detected_mood_action
    if action is None:
        output["mood_action"] = None
    else:
        output["mood_action"] = {
            "kind": action.kind,
            "description": action.description,
            "mood_id": action.mood_id,
            "close_mood_id": action.close_mood_id,
        }

    return {"output": output}
