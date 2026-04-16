"""VibeVoice sound effect provider — generates silent WAV files for free eval runs.

Used by the VibeVoice listening eval workflow as a zero-cost replacement for
Stable Audio / ElevenLabs sound effect providers.  VibeVoice only supports TTS;
sound effect generation is not natively supported, so this provider produces
valid WAV files containing silence so the downstream ``AudioOrchestrator`` can
mix and stitch without errors.
"""
import struct
import wave
from pathlib import Path
from typing import Optional

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider

logger = structlog.get_logger(__name__)

_SAMPLE_RATE = 24000
_CHANNELS = 1
_SAMPLE_WIDTH = 2  # 16-bit PCM


class VibeVoiceSoundEffectProvider(SoundEffectProvider):
    """VibeVoice sound effect provider that writes silent WAV files.

    VibeVoice does not natively support sound effect generation.
    This provider produces silent WAV stubs so the eval pipeline can
    run end-to-end at zero cost — no API calls, no network, no model.
    """

    def generate(
        self,
        description: str,
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Write a silent WAV file of the requested duration.

        Args:
            description: Ignored (logged for traceability).
            output_path: Where to write the silent WAV.
            duration_seconds: Duration of silence in seconds.

        Returns:
            *output_path* on success, ``None`` on failure.
        """
        logger.debug(
            "vibevoice_sfx_generate",
            description=description,
            duration_seconds=duration_seconds,
            output_path=str(output_path),
        )

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            num_frames = int(_SAMPLE_RATE * duration_seconds)
            silent_frames = struct.pack(f"<{num_frames}h", *([0] * num_frames))

            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(_CHANNELS)
                wf.setsampwidth(_SAMPLE_WIDTH)
                wf.setframerate(_SAMPLE_RATE)
                wf.writeframes(silent_frames)

            return output_path
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "vibevoice_sfx_generate_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None
