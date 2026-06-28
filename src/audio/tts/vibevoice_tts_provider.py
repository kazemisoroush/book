"""VibeVoice TTS provider backed by a SageMaker endpoint."""
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import boto3
import lameenc
import numpy as np
import soundfile as sf
import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.repository.artifact_repository import ArtifactRepository

logger = structlog.get_logger(__name__)

_SAMPLE_RATE = 24000
_GAP_SECONDS = 0.3
_MAX_CHUNK_CHARS = 350
_DEFAULT_CFG_SCALE = 1.3

# Neutral voices first so a narrator never gets the accented voice; Samuel stays last.
VOICES: list[dict[str, Any]] = [
    {"voice_id": "en-Carter_man", "name": "Carter", "labels": {"gender": "male"}},
    {"voice_id": "en-Frank_man", "name": "Frank", "labels": {"gender": "male"}},
    {"voice_id": "en-Alice_woman", "name": "Alice", "labels": {"gender": "female"}},
    {"voice_id": "en-Maya_woman", "name": "Maya", "labels": {"gender": "female"}},
    {"voice_id": "in-Samuel_man", "name": "Samuel", "labels": {"gender": "male"}},
]


class VibeVoiceTTSProvider(TTSProvider):
    """Renders beats by calling a VibeVoice SageMaker endpoint."""

    @property
    def name(self) -> str:
        return "vibevoice"

    def __init__(
        self,
        endpoint_name: str,
        region: str,
        books_dir: Path = Path("books"),
        request_log: Optional[ArtifactRepository] = None,
        cfg_scale: float = _DEFAULT_CFG_SCALE,
        client: Optional[Any] = None,
    ) -> None:
        if not endpoint_name:
            raise ValueError("endpoint_name cannot be empty")
        self._endpoint_name = endpoint_name
        self._books_dir = books_dir
        self._request_log = request_log
        self._cfg_scale = cfg_scale
        self._beat_counter = 0
        self._client = client or boto3.client(
            "sagemaker-runtime", region_name=region,
        )

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise one beat to an mp3 and return None."""
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
        self, beat: Beat, voice_id: str, output_path: Path,
    ) -> Optional[str]:
        chunks = _split_text(beat.text, _MAX_CHUNK_CHARS)
        if self._request_log is not None:
            self._request_log.save_request(
                key=_request_key(output_path, self._books_dir),
                method="POST",
                url=f"sagemaker:{self._endpoint_name}",
                headers={},
                body={"voice": voice_id, "chunks": len(chunks), "text": beat.text},
            )

        logger.info(
            "vibevoice_synthesize_start",
            voice_id=voice_id,
            text_length=len(beat.text),
            chunks=len(chunks),
            output_path=str(output_path),
        )

        try:
            waveforms = [self._invoke(chunk, voice_id) for chunk in chunks]
            output_path.write_bytes(_encode_mp3(_concatenate(waveforms)))
            logger.info("vibevoice_synthesize_done", output_path=str(output_path))
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "vibevoice_synthesize_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _invoke(self, text: str, voice_id: str) -> np.ndarray:
        response = self._client.invoke_endpoint(
            EndpointName=self._endpoint_name,
            ContentType="application/json",
            Accept="audio/wav",
            Body=json.dumps(
                {"text": text, "voice": voice_id, "cfg_scale": self._cfg_scale},
            ),
        )
        waveform, _ = sf.read(io.BytesIO(response["Body"].read()), dtype="float32")
        return waveform.mean(axis=1) if waveform.ndim > 1 else waveform

    def get_voices(self) -> list[dict[str, Any]]:
        """Return the available reference voices with gender labels."""
        return [dict(voice) for voice in VOICES]


def _split_text(text: str, max_chars: int) -> list[str]:
    """Group sentences into chunks that stay under the invoke limit."""
    stripped = text.strip()
    sentences = re.findall(r"[^.!?]+[.!?]*\s*", stripped) or [stripped]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = current + sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks or [stripped]


def _concatenate(waveforms: list[np.ndarray]) -> np.ndarray:
    """Join waveforms with a short silence gap between them."""
    gap = np.zeros(int(_SAMPLE_RATE * _GAP_SECONDS), dtype=np.float32)
    pieces: list[np.ndarray] = []
    for waveform in waveforms:
        if pieces:
            pieces.append(gap)
        pieces.append(waveform)
    return np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)


def _encode_mp3(audio: np.ndarray) -> bytes:
    """Encode a float32 mono waveform to mp3 bytes."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(_SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(pcm.tobytes()) + encoder.flush()


def _request_key(output_path: Path, books_dir: Path) -> str:
    """Storage key for the request-log sidecar next to the output."""
    return (
        output_path.with_suffix(".request.json")
        .relative_to(books_dir).as_posix()
    )
