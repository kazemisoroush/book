"""Tests for the VibeVoice TTS provider."""
import io
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf

from src.audio.tts.vibevoice_tts_provider import VibeVoiceTTSProvider, _split_text
from src.domain.beat import Beat, BeatType


def _beat(text: str, voice_id: str | None = "en-Carter_man") -> Beat:
    return Beat(text=text, beat_type=BeatType.NARRATION, character_id=1, voice_id=voice_id)


def _wav_bytes(seconds: float = 0.1, sample_rate: int = 24000) -> bytes:
    data = np.zeros(int(sample_rate * seconds), dtype="float32")
    buffer = io.BytesIO()
    sf.write(buffer, data, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def _mock_client() -> Mock:
    client = Mock()
    body = Mock()
    body.read.return_value = _wav_bytes()
    client.invoke_endpoint.return_value = {"Body": body}
    return client


def test_provide_writes_mp3_under_book_dir(tmp_path: Path) -> None:
    # Arrange
    client = _mock_client()
    provider = VibeVoiceTTSProvider(
        endpoint_name="ep", region="us-east-1", books_dir=tmp_path, client=client,
    )

    # Act
    result = provider.provide(_beat("Hello world."), "book")

    # Assert
    output_path = tmp_path / "book" / "audio" / "tts" / "vibevoice" / "beat_0001.mp3"
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert result is None


def test_provide_returns_none_when_voice_id_missing(tmp_path: Path) -> None:
    # Arrange
    client = _mock_client()
    provider = VibeVoiceTTSProvider(
        endpoint_name="ep", region="us-east-1", books_dir=tmp_path, client=client,
    )
    beat = Beat(text="Hi.", beat_type=BeatType.NARRATION, character_id=1, voice_id=None)

    # Act
    result = provider.provide(beat, "book")

    # Assert
    assert result is None
    client.invoke_endpoint.assert_not_called()


def test_provide_skips_when_audio_already_exists(tmp_path: Path) -> None:
    # Arrange
    client = _mock_client()
    provider = VibeVoiceTTSProvider(
        endpoint_name="ep", region="us-east-1", books_dir=tmp_path, client=client,
    )
    existing = tmp_path / "book" / "audio" / "tts" / "vibevoice" / "beat_0001.mp3"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"already here")

    # Act
    result = provider.provide(_beat("Hello."), "book")

    # Assert
    assert result is None
    client.invoke_endpoint.assert_not_called()


def test_provide_chunks_long_text_into_multiple_calls(tmp_path: Path) -> None:
    # Arrange
    client = _mock_client()
    provider = VibeVoiceTTSProvider(
        endpoint_name="ep", region="us-east-1", books_dir=tmp_path, client=client,
    )
    sentence = "This is a fairly long sentence used to push the chunker over its limit. "
    long_text = sentence * 8

    # Act
    provider.provide(_beat(long_text), "book")

    # Assert
    assert client.invoke_endpoint.call_count > 1
    output_path = tmp_path / "book" / "audio" / "tts" / "vibevoice" / "beat_0001.mp3"
    assert output_path.exists()


def test_split_text_breaks_an_over_long_single_sentence() -> None:
    # Arrange
    one_long_sentence = ("word " * 200).strip()

    # Act
    chunks = _split_text(one_long_sentence, 100)

    # Assert
    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_empty_endpoint_name_raises_valueerror() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="endpoint_name cannot be empty"):
        VibeVoiceTTSProvider(endpoint_name="", region="us-east-1")
