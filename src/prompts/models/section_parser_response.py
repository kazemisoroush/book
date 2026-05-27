"""Pydantic model for the AI section parser's JSON response."""
from typing import Optional

from pydantic import BaseModel, Field


class BeatItem(BaseModel):
    """One beat as emitted by the LLM."""

    type: str
    text: str = ""
    speaker: Optional[str] = None
    emotion: Optional[str] = None
    voice_stability: Optional[float] = None
    voice_style: Optional[float] = None
    voice_speed: Optional[float] = None


class NewCharacterItem(BaseModel):
    """A previously-unseen character emitted by the LLM."""

    character_id: Optional[str] = None
    name: str = ""
    sex: Optional[str] = None
    age: Optional[str] = None
    description: Optional[str] = None


class DescriptionUpdate(BaseModel):
    """A revised description for an existing character."""

    character_id: Optional[str] = None
    description: Optional[str] = None


class SceneItem(BaseModel):
    """The scene/environment detected for this section."""

    environment: str = "unknown"
    acoustic_hints: list[str] = Field(default_factory=list)
    voice_modifiers: dict[str, float] = Field(default_factory=dict)
    ambient_prompt: Optional[str] = None
    ambient_volume: Optional[float] = None


class SectionParserResponse(BaseModel):
    """Full JSON response from the section parser prompt."""

    beats: list[BeatItem] = Field(default_factory=list)
    new_characters: list[NewCharacterItem] = Field(default_factory=list)
    character_description_updates: list[DescriptionUpdate] = Field(default_factory=list)
    scene: Optional[SceneItem] = None
