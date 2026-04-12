"""ElevenLabs Voice Design API integration.

Generates bespoke voices for characters using the Voice Design API.
The flow is:

1. ``POST /v1/text-to-voice/create-previews`` with the voice description
   and a fixed preview text -- returns 3 preview options.
2. Take the first preview's ``generated_voice_id``.
3. ``POST /v1/text-to-voice/create-voice`` to convert the preview into a
   permanent voice -- returns a ``Voice`` with ``voice_id``.

The fixed preview text keeps synthesis deterministic across runs.  Choosing
among previews requires human judgement; for an automated pipeline the first
preview is sufficient.
"""
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = (
    "The morning light filtered through the window as she poured the tea. "
    "Outside, the birds were singing and the garden was beginning to bloom with colour."
)


def design_voice(description: str, character_name: str, client: Any) -> str:
    """Generate a custom ElevenLabs voice from a text description.

    Args:
        description: The voice design prompt (e.g. ``"adult male, booming
                     bass voice, thick West Country accent."``).
        character_name: Human-readable name used as the voice name in
                        ElevenLabs.
        client: An initialised ``ElevenLabs`` SDK client instance.

    Returns:
        The permanent ``voice_id`` for the newly created voice.

    Raises:
        Any exception propagated from the ElevenLabs SDK (callers should
        catch and fall back to demographic matching).
    """
    logger.info(
        "voice_design_create_previews",
        character_name=character_name,
        description=description,
    )

    preview_response = client.text_to_voice.create_previews(
        voice_description=description,
        text=_PREVIEW_TEXT,
    )

    generated_voice_id = preview_response.previews[0].generated_voice_id

    logger.info(
        "voice_design_create_voice",
        character_name=character_name,
        generated_voice_id=generated_voice_id,
    )

    voice = client.text_to_voice.create(
        voice_name=character_name,
        voice_description=description,
        generated_voice_id=generated_voice_id,
    )

    logger.info(
        "voice_design_complete",
        character_name=character_name,
        voice_id=voice.voice_id,
    )

    return str(voice.voice_id)
