"""ElevenLabs implementation of SoundEffectProvider."""
from typing import Any

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.beat import Beat
from src.storage.audio_store import AudioStore
from src.storage.objects import SFXBeat, SFXBeatRef

logger = structlog.get_logger(__name__)


class ElevenLabsSoundEffectProvider(SoundEffectProvider):
    """ElevenLabs sound effect provider using the Sound Effects API."""

    @property
    def name(self) -> str:
        return "elevenlabs"

    def __init__(self, client: Any, audio_store: AudioStore) -> None:
        self._client = client
        self._audio_store = audio_store
        self._beat_counter = 0

    def provide(self, beat: Beat, book_id: str) -> None:
        self._beat_counter += 1
        ref = SFXBeatRef(book_id=book_id, provider=self.name, index=self._beat_counter)
        self._generate(beat.text, ref)

    def _generate(
        self,
        description: str,
        ref: SFXBeatRef,
        duration_seconds: float = 2.0,
    ) -> bool:
        """Generate a sound effect, skipping the API call if the artifact already exists."""
        if self._audio_store.has_sfx_beat(ref):
            logger.debug("sound_effect_cache_hit", ref=ref)
            return True

        try:
            logger.debug(
                "sound_effect_api_call",
                description=description,
                duration_seconds=duration_seconds,
            )
            audio_iter = self._client.text_to_sound_effects.convert(
                text=description,
                duration_seconds=duration_seconds,
            )
            audio_data = b"".join(audio_iter)
            self._audio_store.save_sfx_beat(SFXBeat(
                book_id=ref.book_id,
                provider=ref.provider,
                index=ref.index,
                audio=audio_data,
                extension=ref.extension,
            ))
            logger.debug(
                "sound_effect_generated",
                description=description,
                ref=ref,
                size_bytes=len(audio_data),
            )
            return True

        except Exception as e:
            logger.warning(
                "sound_effect_api_failed",
                description=description,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
