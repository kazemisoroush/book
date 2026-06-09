"""Tests for ElevenLabsCharacterProvider."""
import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.characters.elevenlabs_character_provider import ElevenLabsCharacterProvider
from src.domain.character import Character

_BOOK_ID = "book:author"


def _preview(generated_voice_id: str, audio_bytes: bytes) -> MagicMock:
    preview = MagicMock()
    preview.generated_voice_id = generated_voice_id
    preview.audio_base_64 = base64.b64encode(audio_bytes).decode("ascii")
    preview.media_type = "audio/mpeg"
    return preview


def _designing_client(designed_voice_id: str) -> MagicMock:
    client = MagicMock()
    client.voices.search.return_value = MagicMock(voices=[])
    client.text_to_voice.create_previews.return_value = MagicMock(
        previews=[_preview("gen_id", b"\x00\x01\x02")],
    )
    client.text_to_voice.create.return_value = MagicMock(voice_id=designed_voice_id)
    return client


class TestUpsert:
    """upsert designs a new voice on cache miss and reuses it on cache hit."""

    def test_returns_existing_voice_id_on_cache_hit(self) -> None:
        # Arrange
        client = MagicMock()
        existing_voice = MagicMock()
        existing_voice.name = "book:author:harry_potter"
        existing_voice.voice_id = "v_existing"
        client.voices.search.return_value = MagicMock(voices=[existing_voice])
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))
        character = Character(
            id=2, name="Harry Potter",
            description="brave young wizard", sex="male", age="young",
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "v_existing"
        client.text_to_voice.create.assert_not_called()

    def test_designs_voice_on_cache_miss(self, tmp_path: Path) -> None:
        # Arrange
        client = _designing_client("v_new")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            id=3, name="Hagrid",
            description="booming bass voice, thick West Country accent",
            sex="male", age="adult",
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "v_new"
        create_kwargs = client.text_to_voice.create.call_args.kwargs
        assert create_kwargs["voice_name"] == "book:author:hagrid"
        assert "Age: adult." in create_kwargs["voice_description"]
        assert "Sex: male." in create_kwargs["voice_description"]
        assert create_kwargs["generated_voice_id"] == "gen_id"

    def test_saves_every_preview_to_disk_on_cache_miss(self, tmp_path: Path) -> None:
        # Arrange
        client = MagicMock()
        client.voices.search.return_value = MagicMock(voices=[])
        client.text_to_voice.create_previews.return_value = MagicMock(previews=[
            _preview("gen_0", b"\xaa\xbb"),
            _preview("gen_1", b"\xcc\xdd"),
        ])
        client.text_to_voice.create.return_value = MagicMock(voice_id="v_new")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            id=4, name="Alexei Ivanovich",
            description="intense Russian tutor", sex="male", age="adult",
        )

        # Act
        provider.upsert(character, "the_gambler:fyodor_dostoyevsky")

        # Assert
        voices_dir = tmp_path / "the_gambler:fyodor_dostoyevsky" / "voices" / "alexei_ivanovich"
        assert (voices_dir / "preview_0.mp3").read_bytes() == b"\xaa\xbb"
        assert (voices_dir / "preview_1.mp3").read_bytes() == b"\xcc\xdd"

    def test_raises_when_character_has_no_description(self) -> None:
        # Arrange
        client = _designing_client("v_narr")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))
        character = Character(id=5, name="Silent")

        # Act / Assert
        with pytest.raises(ValueError, match="no voice description"):
            provider.upsert(character, _BOOK_ID)
        client.text_to_voice.create.assert_not_called()
