"""Fish Audio TTS provider."""
import os
from pathlib import Path
from typing import Any, Optional

import requests
import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.stores.api_request_log import APIRequestLog

logger = structlog.get_logger(__name__)


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio TTS provider."""

    @property
    def name(self) -> str:
        return "fish_audio"

    def __init__(
        self,
        api_key: str,
        books_dir: Path = Path("books"),
        base_url: str = "https://api.fish.audio/v1",
        request_log: Optional[APIRequestLog] = None,
    ) -> None:
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.api_key = api_key
        self._books_dir = books_dir
        self.base_url = base_url
        self._beat_counter = 0
        self._request_log = request_log

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise one *beat*."""
        if beat.voice_id is None:
            return None
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        if output_path.exists() and output_path.stat().st_size > 0:
            return None
        return self._synthesize(beat, beat.voice_id, output_path)

    def _synthesize(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
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
            output_path=str(output_path),
        )

        if self._request_log is not None:
            self._request_log.save_request(
                key=_request_key(output_path, self._books_dir),
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


def _request_key(output_path: Path, books_dir: Path) -> str:
    """Storage key for the request-log sidecar next to *output_path*."""
    return (
        output_path.with_suffix(".request.json")
        .relative_to(books_dir).as_posix()
    )
