"""Fish Audio TTS provider."""
from typing import Any, Optional

import requests
import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.repository.api_artifact_store import APIArtifactStore
from src.storage.audio_store import AudioStore

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
        artifact_store: Optional[APIArtifactStore] = None,
    ) -> None:
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.api_key = api_key
        self._audio_store = audio_store
        self.base_url = base_url
        self._beat_counter = 0
        self._artifact_store = artifact_store

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise one *beat*."""
        if beat.voice_id is None:
            return None
        self._beat_counter += 1
        beat_key = self._audio_store.tts_beat_key(book_id, self.name, self._beat_counter)

        if self._audio_store.exists(beat_key):
            return None
        return self._synthesize(beat, beat.voice_id, beat_key)

    def _synthesize(
        self,
        beat: Beat,
        voice_id: str,
        beat_key: str,
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
            beat_key=beat_key,
        )

        if self._artifact_store is not None:
            self._artifact_store.save_request(
                key=_request_key(beat_key),
                method="POST",
                url=endpoint,
                headers=headers,
                body=request_body,
            )

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=request_body,
                timeout=60,
            )
            response.raise_for_status()
            self._audio_store.write_bytes(beat_key, response.content)
            logger.info("fish_audio_synthesize_done", beat_key=beat_key)
            return None

        except requests.RequestException as e:
            logger.warning(
                "fish_audio_synthesize_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e.response, "status_code", None),
            )
            return None


def _request_key(beat_key: str) -> str:
    """Sibling artifact key with .request.json extension."""
    return beat_key.removesuffix(".mp3") + ".request.json"
