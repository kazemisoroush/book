"""ElevenLabs Voice Design API integration."""
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = (
    "The morning light filtered through the window as she poured the tea. "
    "Outside, the birds were singing and the garden was beginning to bloom with colour."
)


def design_voice(description: str, voice_name: str, client: Any) -> str:
    """Generate a custom ElevenLabs voice from *description* and return its ``voice_id``."""
    logger.info(
        "voice_design_create_previews",
        voice_name=voice_name,
        description=description,
    )

    preview_response = client.text_to_voice.create_previews(
        voice_description=description,
        text=_PREVIEW_TEXT,
    )

    generated_voice_id = preview_response.previews[0].generated_voice_id

    logger.info(
        "voice_design_create_voice",
        voice_name=voice_name,
        generated_voice_id=generated_voice_id,
    )

    voice = client.text_to_voice.create(
        voice_name=voice_name,
        voice_description=description,
        generated_voice_id=generated_voice_id,
    )

    logger.info(
        "voice_design_complete",
        voice_name=voice_name,
        voice_id=voice.voice_id,
    )

    return str(voice.voice_id)
