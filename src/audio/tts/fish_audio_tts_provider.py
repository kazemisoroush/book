"""Fish Audio TTS provider."""
from typing import Any, Optional

import requests
import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.storage.audio_store import AudioStore
from src.storage.objects import APIRequest, TTSBeat, TTSBeatRef

logger = structlog.get_logger(__name__)


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio TTS provider."""

    @property
    def name(self) -> str:
        return "fish_audio"

    def __init__(
        self,
        api_key: str,
        audio_store: AudioStore,
        base_url: str = "https://api.fish.audio/v1",
    ) -> None:
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.api_key = api_key
        self._audio_store = audio_store
        self.base_url = base_url
        self._beat_counter = 0

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        if beat.voice_id is None:
            return None
        self._beat_counter += 1
        ref = TTSBeatRef(book_id=book_id, provider=self.name, index=self._beat_counter)

        if self._audio_store.has_tts_beat(ref):
            return None
        return self._synthesize(beat, beat.voice_id, ref)

    def _synthesize(
        self,
        beat: Beat,
        voice_id: str,
        ref: TTSBeatRef,
    ) -> Optional[str]:
        request_body: dict[str, Any] = {
            "text": beat.text,
            "reference_id": voice_id,
        }
        if beat.emotion:
            request_body["emotion"] = beat.emotion

        endpoint = f"{self.base_url}/tts"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        logger.info(
            "fish_audio_synthesize_start",
            voice_id=voice_id,
            text_length=len(beat.text),
            beat_index=ref.index,
        )

        api_request = APIRequest(
            method="POST", url=endpoint, headers=headers, body=request_body,
        )

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=request_body,
                timeout=60,
            )
            response.raise_for_status()
            self._audio_store.save_tts_beat(
                TTSBeat(
                    book_id=ref.book_id,
                    provider=ref.provider,
                    index=ref.index,
                    audio=response.content,
                ),
                api_request=api_request,
            )
            logger.info("fish_audio_synthesize_done", beat_index=ref.index)
            return None

        except requests.RequestException as e:
            logger.warning(
                "fish_audio_synthesize_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e.response, "status_code", None),
            )
            return None
