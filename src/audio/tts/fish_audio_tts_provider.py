"""Fish Audio TTS provider implementation."""
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import requests
import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.repository.api_artifact_store import APIArtifactStore

if TYPE_CHECKING:
    from src.audio.tts.beat_context_resolver import BeatContext

logger = structlog.get_logger(__name__)


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio TTS provider implementation."""

    @property
    def name(self) -> str:
        return "fish_audio"

    def __init__(
        self,
        api_key: str,
        books_dir: Path = Path("books"),
        base_url: str = "https://api.fish.audio/v1",
        artifact_store: Optional[APIArtifactStore] = None,
    ) -> None:
        """Initialize Fish Audio provider."""
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self._books_dir = books_dir
        self.base_url = base_url
        self._beat_counter = 0
        self._artifact_store = artifact_store

    def provide(self, beat: Beat, voice_id: str, book_id: str) -> None:
        """Synthesize speech for a beat."""
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        if not (output_path.exists() and output_path.stat().st_size > 0):
            self.synthesize(beat, voice_id, output_path)

    def synthesize(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        """Synthesize text using Fish Audio API."""
        if context is not None:
            if context.previous_text or context.next_text:
                logger.debug(
                    "fish_audio_prosody_context_not_supported",
                    previous_text_provided=context.previous_text is not None,
                    next_text_provided=context.next_text is not None,
                )
            if context.previous_request_ids:
                logger.debug(
                    "fish_audio_request_continuity_not_supported",
                    previous_request_ids=context.previous_request_ids,
                )

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
            output_path=str(output_path),
        )

        if self._artifact_store is not None:
            self._artifact_store.save_request(
                path=output_path.with_suffix(".request.json"),
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

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            logger.info(
                "fish_audio_synthesize_done",
                output_path=str(output_path),
            )

            return None

        except requests.RequestException as e:
            logger.warning(
                "fish_audio_synthesize_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e.response, "status_code", None),
            )
            return None
