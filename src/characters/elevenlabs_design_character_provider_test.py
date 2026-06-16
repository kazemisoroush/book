"""Tests for ElevenLabsDesignCharacterProvider."""
import base64
from pathlib import Path
from unittest.mock import MagicMock

from src.characters.elevenlabs_design_character_provider import (
    ElevenLabsDesignCharacterProvider,
)
from src.domain.character import Character
from src.repository.api_artifact_store import FileAPIArtifactStore

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
        provider = ElevenLabsDesignCharacterProvider(client=client, books_dir=Path("/tmp"))
        character = Character(
            id=2, name="Harry Potter",
            gender="male", age="young", accent="british",
            descriptives=["brave"],
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "v_existing"
        client.text_to_voice.create.assert_not_called()

    def test_designs_voice_from_derived_description_on_cache_miss(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        client = _designing_client("v_new")
        provider = ElevenLabsDesignCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            id=3, name="Hagrid",
            gender="male", age="middle_aged", accent="british",
            descriptives=["deep", "warm"],
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "v_new"
        create_kwargs = client.text_to_voice.create.call_args.kwargs
        assert create_kwargs["voice_name"] == "book:author:hagrid"
        assert create_kwargs["voice_description"] == character.description
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
        provider = ElevenLabsDesignCharacterProvider(client=client, books_dir=tmp_path)
        character = Character(
            id=4, name="Alexei Ivanovich",
            gender="male", age="young", accent="russian",
            descriptives=["intense"],
        )

        # Act
        provider.upsert(character, "the_gambler:fyodor_dostoyevsky")

        # Assert
        voices_dir = tmp_path / "the_gambler:fyodor_dostoyevsky" / "voices" / "alexei_ivanovich"
        assert (voices_dir / "preview_0.mp3").read_bytes() == b"\xaa\xbb"
        assert (voices_dir / "preview_1.mp3").read_bytes() == b"\xcc\xdd"


class TestRequestArtifacts:
    """When an artifact_store is injected, every Voice Design call is recorded."""

    def test_records_search_previews_and_create_on_cache_miss(self, tmp_path: Path) -> None:
        # Arrange
        client = _designing_client("v_new")
        store = FileAPIArtifactStore()
        provider = ElevenLabsDesignCharacterProvider(
            client=client, books_dir=tmp_path, api_key="sk-secret",
            artifact_store=store,
        )
        character = Character(
            id=7, name="Mrs Bennet",
            gender="female", age="middle_aged", accent="british",
            descriptives=["warm", "breathless"],
        )

        # Act
        provider.upsert(character, "pride_and_prejudice:jane_austen")

        # Assert
        voice_dir = (
            tmp_path / "pride_and_prejudice:jane_austen" / "voices" / "mrs_bennet"
        )
        assert (voice_dir / "search.request.json").exists()
        assert (voice_dir / "create_previews.request.json").exists()
        assert (voice_dir / "create.request.json").exists()
