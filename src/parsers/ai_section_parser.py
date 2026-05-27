"""AI-powered section parser that beats text into dialogue and narration."""
from dataclasses import replace as dc_replace
from typing import Optional

import structlog
from pydantic import ValidationError

from src.ai.ai_provider import AIProvider
from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_NAME, Character
from src.domain.character_id import build_character_id
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Scene,
    SceneRegistry,
    Section,
)
from src.parsers.book_section_parser import BookSectionParser
from src.parsers.text_sanitizer import sanitize_beat_text
from src.prompts.models.section_parser_prompt import SectionParserPrompt
from src.prompts.models.section_parser_response import SectionParserResponse

logger = structlog.get_logger(__name__)


def _strip_markdown_fence(text: str) -> str:
    """Strip ```json / ``` code fences sometimes wrapped around LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


class AISectionParser(BookSectionParser):
    """Uses AI to intelligently beat sections into dialogue and narration."""

    def __init__(self, ai_provider: AIProvider) -> None:
        self.ai_provider = ai_provider
        self.last_detected_scene: Optional[Scene] = None

    def parse(
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        book_id: str,
        book_title: Optional[str] = None,
        book_author: Optional[str] = None,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> tuple[list[Beat], CharacterRegistry]:
        """Parse a section into beats using AI."""
        narrator_cid = build_character_id(book_id, NARRATOR_NAME)

        if section.section_type is not None:
            self.last_detected_scene = None
            beat_type = BeatType.from_string(section.section_type, default=BeatType.OTHER)
            character_id = narrator_cid if beat_type in {
                BeatType.BOOK_TITLE, BeatType.CHAPTER_ANNOUNCEMENT,
            } else None
            return [Beat(
                text=section.text, beat_type=beat_type, character_id=character_id,
            )], registry

        if not section.text.strip():
            self.last_detected_scene = None
            return [], registry

        prompt = SectionParserPrompt.create(
            section.text, registry, context_window,
            book_title=book_title,
            book_author=book_author,
            scene_registry=scene_registry,
        )
        text_preview = section.text[:60].replace("\n", " ")

        response = self.ai_provider.generate(prompt, max_tokens=8192)
        if not response.strip():
            logger.warning(
                "ai_section_parser_empty_response",
                text_preview=text_preview,
            )
            raise ValueError("Empty response from AI provider")

        try:
            parsed = SectionParserResponse.model_validate_json(_strip_markdown_fence(response))
        except ValidationError as e:
            logger.error(
                "ai_section_parser_failed",
                error=str(e),
                text_preview=text_preview,
            )
            raise ValueError(f"Failed to parse AI response as JSON: {e}") from e

        new_characters: list[Character] = []
        llm_id_remap: dict[str, str] = {}
        for c in parsed.new_characters:
            if not c.name:
                continue
            canonical_id = build_character_id(book_id, c.name)
            if c.character_id:
                llm_id_remap[c.character_id] = canonical_id
            new_characters.append(Character(
                character_id=canonical_id,
                name=c.name,
                description=c.description,
                sex=c.sex,
                age=c.age,
            ))

        beats: list[Beat] = []
        for b in parsed.beats:
            beat_type = BeatType.from_string(b.type.lower())
            if beat_type in {BeatType.NARRATION, BeatType.BOOK_TITLE} and b.speaker is None:
                character_id = narrator_cid
            elif beat_type == BeatType.SOUND_EFFECT:
                character_id = None
            elif b.speaker is None:
                character_id = None
            else:
                character_id = llm_id_remap.get(b.speaker, b.speaker)
            beats.append(Beat(
                text=sanitize_beat_text(b.text),
                beat_type=beat_type,
                character_id=character_id,
                emotion=b.emotion if b.emotion else None,
                voice_stability=b.voice_stability,
                voice_style=b.voice_style,
                voice_speed=b.voice_speed,
            ))

        beats = [
            b for b in beats
            if b.is_narratable
            or b.beat_type == BeatType.SOUND_EFFECT
            or b.beat_type == BeatType.VOCAL_EFFECT
        ]

        description_updates: list[tuple[str, str]] = [
            (llm_id_remap.get(u.character_id, u.character_id), u.description)
            for u in parsed.character_description_updates
            if u.character_id and u.description
        ]

        detected_scene: Optional[Scene] = None
        if parsed.scene is not None:
            s = parsed.scene
            detected_scene = Scene(
                scene_id=f"scene_{s.environment}",
                environment=s.environment,
                acoustic_hints=list(s.acoustic_hints),
                voice_modifiers=dict(s.voice_modifiers),
                ambient_prompt=s.ambient_prompt,
                ambient_volume=s.ambient_volume,
            )
        self.last_detected_scene = detected_scene

        if detected_scene is not None and scene_registry is not None:
            scene_registry.upsert(detected_scene)
            for seg in beats:
                seg.scene_id = detected_scene.scene_id

        for char in new_characters:
            registry.upsert(char)
        for char_id, new_description in description_updates:
            existing = registry.get(char_id)
            if existing is not None:
                registry.upsert(dc_replace(existing, description=new_description))

        logger.debug(
            "ai_section_parsed",
            beat_count=len(beats),
            new_character_count=len(new_characters),
            description_update_count=len(description_updates),
            text_preview=text_preview,
        )
        return beats, registry
