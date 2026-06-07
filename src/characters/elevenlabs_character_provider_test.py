"""Tests for ElevenLabsCharacterProvider."""
import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.characters.elevenlabs_character_provider import ElevenLabsCharacterProvider
from src.domain.character import Character
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
)


def _make_book(characters: list[Character]) -> Book:
    metadata = BookMetadata(
        title="T", author=None, releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    return Book(
        metadata=metadata,
        content=BookContent(chapters=[]),
        character_registry=CharacterRegistry(characters=list(characters)),
    )


def _preview(generated_voice_id: str, audio_bytes: bytes) -> MagicMock:
    preview = MagicMock()
    preview.generated_voice_id = generated_voice_id
    preview.audio_base_64 = base64.b64encode(audio_bytes).decode("ascii")
    preview.media_type = "audio/mpeg"
    return preview


def _designing_client(designed_voice_id: str) -> MagicMock:
    """Return a mock ElevenLabs client that returns *designed_voice_id* from voice design."""
    client = MagicMock()
    client.voices.get_all.return_value = MagicMock(voices=[])
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
        existing_voice.name = "book:harry_potter"
        existing_voice.voice_id = "v_existing"
        client.voices.get_all.return_value = MagicMock(voices=[existing_voice])
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))
        character = Character(
            character_id="book:harry_potter", name="Harry Potter",
            description="brave young wizard", sex="male", age="young",
        )

        # Act
        voice_id = provider.upsert(character)

        # Assert
        assert voice_id == "v_existing"
        client.text_to_voice.create.assert_not_called()

    def test_designs_voice_on_cache_miss(self, tmp_path: Path) -> None:
        # Arrange
        client = _designing_client("v_new")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            character_id="book:hagrid", name="Hagrid",
            description="booming bass voice, thick West Country accent",
            sex="male", age="adult",
        )

        # Act
        voice_id = provider.upsert(character)

        # Assert
        assert voice_id == "v_new"
        create_kwargs = client.text_to_voice.create.call_args.kwargs
        assert create_kwargs["voice_name"] == "book:hagrid"
        assert "Age: adult." in create_kwargs["voice_description"]
        assert "Sex: male." in create_kwargs["voice_description"]
        assert create_kwargs["generated_voice_id"] == "gen_id"

    def test_saves_every_preview_to_disk_on_cache_miss(self, tmp_path: Path) -> None:
        """All previews returned by ElevenLabs are decoded and persisted under the book directory."""
        # Arrange
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[])
        client.text_to_voice.create_previews.return_value = MagicMock(previews=[
            _preview("gen_0", b"\xaa\xbb"),
            _preview("gen_1", b"\xcc\xdd"),
            _preview("gen_2", b"\xee\xff"),
        ])
        client.text_to_voice.create.return_value = MagicMock(voice_id="v_new")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            character_id="the_gambler:fyodor_dostoyevsky:alexei_ivanovich",
            name="Alexei Ivanovich",
            description="intense Russian tutor",
            sex="male", age="adult",
        )

        # Act
        provider.upsert(character)

        # Assert
        voices_dir = tmp_path / "the_gambler:fyodor_dostoyevsky" / "voices" / "alexei_ivanovich"
        assert (voices_dir / "preview_0.mp3").read_bytes() == b"\xaa\xbb"
        assert (voices_dir / "preview_1.mp3").read_bytes() == b"\xcc\xdd"
        assert (voices_dir / "preview_2.mp3").read_bytes() == b"\xee\xff"

    def test_writes_no_preview_files_on_cache_hit(self, tmp_path: Path) -> None:
        """Cache hits skip preview generation entirely and leave the disk untouched."""
        # Arrange
        client = MagicMock()
        existing = MagicMock()
        existing.name = "book:harry_potter"
        existing.voice_id = "v_existing"
        client.voices.get_all.return_value = MagicMock(voices=[existing])
        provider = ElevenLabsCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            character_id="book:harry_potter", name="Harry Potter",
            description="brave young wizard", sex="male", age="young",
        )

        # Act
        provider.upsert(character)

        # Assert
        assert list(tmp_path.iterdir()) == []
        client.text_to_voice.create_previews.assert_not_called()

    def test_raises_when_character_has_no_description(self) -> None:
        # Arrange
        client = _designing_client("v_narr")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))
        character = Character(character_id="book:silent", name="Silent")

        # Act / Assert
        with pytest.raises(ValueError, match="no voice description"):
            provider.upsert(character)
        client.text_to_voice.create.assert_not_called()


class TestGetAll:
    """get_all queries ElevenLabs for voices prefixed with the book id."""

    def _voice(self, name: str, voice_id: str) -> MagicMock:
        v = MagicMock()
        v.name = name
        v.voice_id = voice_id
        return v

    def _book_with_metadata(self, title: str, author: str) -> Book:
        return Book(
            metadata=BookMetadata(
                title=title, author=author, releaseDate=None,
                language=None, originalPublication=None, credits=None,
            ),
            content=BookContent(chapters=[]),
            character_registry=CharacterRegistry(),
        )

    def test_returns_voices_matching_book_prefix(self) -> None:
        # Arrange
        book = self._book_with_metadata("Pride and Prejudice", "Jane Austen")
        prefix = "pride_and_prejudice:jane_austen:"
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[
            self._voice(f"{prefix}narrator", "v_narr"),
            self._voice(f"{prefix}elizabeth_bennet", "v_eliza"),
        ])
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))

        # Act
        result = provider.get_all(book)

        # Assert
        assert result == {
            f"{prefix}narrator": "v_narr",
            f"{prefix}elizabeth_bennet": "v_eliza",
        }
        client.voices.get_all.assert_called_once_with(search=prefix)

    def test_filters_out_voices_not_matching_book_prefix(self) -> None:
        # Arrange. ElevenLabs search is fuzzy; results may include partial matches.
        book = self._book_with_metadata("The Book", "Author")
        prefix = "the_book:author:"
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[
            self._voice(f"{prefix}alice", "v_alice"),
            self._voice("other_book:other_author:narrator", "v_other"),
        ])
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))

        # Act
        result = provider.get_all(book)

        # Assert
        assert result == {f"{prefix}alice": "v_alice"}

    def test_returns_empty_when_vendor_lookup_fails(self) -> None:
        # Arrange
        book = self._book_with_metadata("The Book", "Author")
        client = MagicMock()
        client.voices.get_all.side_effect = RuntimeError("boom")
        provider = ElevenLabsCharacterProvider(client=client, books_dir=Path("/tmp"))

        # Act
        result = provider.get_all(book)

        # Assert
        assert result == {}
