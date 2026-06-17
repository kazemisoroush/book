"""Tests for ElevenLabsDialogueProvider."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.audio.tts.elevenlabs_dialogue_provider import (
    ElevenLabsDialogueProvider,
    _chunk_beats,
)
from src.domain.beat import Beat, BeatType
from src.domain.models import Chapter


def _beat(
    text: str,
    voice_id: str | None = "v1",
    btype: BeatType = BeatType.NARRATION,
    emotion: str | None = None,
) -> Beat:
    return Beat(
        text=text, beat_type=btype, character_id=1,
        voice_id=voice_id, emotion=emotion,
    )


@dataclass
class _FakeRawResponse:
    headers: dict[str, str]
    data: list[bytes]

    def __enter__(self) -> "_FakeRawResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None


@dataclass
class _RecordedCall:
    inputs: list[dict[str, str]]
    model_id: str


@dataclass
class _FakeRawClient:
    calls: list[_RecordedCall] = field(default_factory=list)
    next_request_id: int = 1

    def convert(self, *, inputs: list[dict[str, str]], model_id: str) -> _FakeRawResponse:
        self.calls.append(_RecordedCall(inputs=list(inputs), model_id=model_id))
        request_id = f"req-{self.next_request_id}"
        self.next_request_id += 1
        return _FakeRawResponse(headers={"request-id": request_id}, data=[b"\x00\x00"])


@dataclass
class _FakeTextToDialogueClient:
    with_raw_response: _FakeRawClient


@dataclass
class _FakeElevenLabsClient:
    text_to_dialogue: _FakeTextToDialogueClient


def _provider_with_fake_client(books_dir: Path) -> tuple[ElevenLabsDialogueProvider, _FakeRawClient]:
    raw = _FakeRawClient()
    fake = _FakeElevenLabsClient(
        text_to_dialogue=_FakeTextToDialogueClient(with_raw_response=raw),
    )
    provider = ElevenLabsDialogueProvider(api_key="k", books_dir=books_dir)
    provider._client = fake
    return provider, raw


class TestChunkBeats:
    """_chunk_beats respects the 2000-char and 10-voice caps."""

    def test_collects_single_chunk_when_under_limits(self) -> None:
        # Arrange
        beats = [_beat("hello"), _beat("there", voice_id="v2")]

        # Act
        chunks = _chunk_beats(beats)

        # Assert
        assert chunks == [beats]

    def test_skips_non_narratable_beats(self) -> None:
        # Arrange
        beats = [
            _beat("ok"),
            _beat("noise", btype=BeatType.SOUND_EFFECT),
        ]

        # Act
        chunks = _chunk_beats(beats)

        # Assert
        assert len(chunks) == 1
        assert [b.text for b in chunks[0]] == ["ok"]

    def test_skips_beats_with_no_voice_id(self) -> None:
        # Arrange
        beats = [_beat("ok"), _beat("missing", voice_id=None)]

        # Act
        chunks = _chunk_beats(beats)

        # Assert
        assert [b.text for chunk in chunks for b in chunk] == ["ok"]

    def test_splits_when_char_limit_would_overflow(self) -> None:
        # Arrange
        beats = [_beat("a" * 1500), _beat("b" * 800)]

        # Act
        chunks = _chunk_beats(beats)

        # Assert
        assert len(chunks) == 2
        assert chunks[0][0].text == "a" * 1500
        assert chunks[1][0].text == "b" * 800

    def test_splits_when_unique_voice_limit_would_overflow(self) -> None:
        # Arrange
        beats = [_beat("hi", voice_id=f"v{i}") for i in range(11)]

        # Act
        chunks = _chunk_beats(beats)

        # Assert
        assert len(chunks) == 2
        assert len({b.voice_id for b in chunks[0]}) == 10
        assert len(chunks[1]) == 1


class TestProvideCollection:
    """provide_collection calls the dialogue endpoint once per chunk."""

    def test_single_chunk_one_call(self, tmp_path: Path) -> None:
        # Arrange
        provider, raw = _provider_with_fake_client(tmp_path)
        beats = [_beat("hello"), _beat("there", voice_id="v2")]

        # Act
        request_ids = provider.provide_collection(Chapter(number=1, title='', beats=beats), book_id="alice")

        # Assert
        assert len(raw.calls) == 1
        assert raw.calls[0].inputs == [
            {"text": "hello", "voice_id": "v1"},
            {"text": "there", "voice_id": "v2"},
        ]
        assert request_ids == ["req-1", "req-1"]

    def test_two_chunks_two_calls(self, tmp_path: Path) -> None:
        # Arrange
        provider, raw = _provider_with_fake_client(tmp_path)
        beats = [_beat("a" * 1500), _beat("b" * 800)]

        # Act
        request_ids = provider.provide_collection(Chapter(number=1, title='', beats=beats), book_id="alice")

        # Assert
        assert len(raw.calls) == 2
        assert request_ids == ["req-1", "req-2"]

    def test_wraps_non_neutral_emotion_as_inline_tag(self, tmp_path: Path) -> None:
        # Arrange
        provider, raw = _provider_with_fake_client(tmp_path)
        beats = [
            _beat("I refuse!", emotion="ANGRY"),
            _beat("Fine.", emotion="neutral"),
            _beat("Hello.", emotion=None),
        ]

        # Act
        provider.provide_collection(
            Chapter(number=1, title='', beats=beats), book_id="alice",
        )

        # Assert
        assert raw.calls[0].inputs == [
            {"text": "[angry] I refuse!", "voice_id": "v1"},
            {"text": "Fine.", "voice_id": "v1"},
            {"text": "Hello.", "voice_id": "v1"},
        ]

    def test_writes_one_mp3_per_chunk_under_book_dir(self, tmp_path: Path) -> None:
        # Arrange
        provider, _ = _provider_with_fake_client(tmp_path)
        beats = [_beat("a" * 1500), _beat("b" * 800)]

        # Act
        provider.provide_collection(Chapter(number=1, title='', beats=beats), book_id="alice")

        # Assert
        out_dir = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_dialogue" / "chapter_001"
        assert (out_dir / "chunk_0001.mp3").exists()
        assert (out_dir / "chunk_0002.mp3").exists()
