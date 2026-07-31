"""Tests for ElevenLabsLibraryCharacterProvider."""
from unittest.mock import MagicMock

import pytest

from src.characters.elevenlabs_library_character_provider import (
    ElevenLabsLibraryCharacterProvider,
)
from src.domain.character import Character

_BOOK_ID = "book:author"


def _shared_voice(
    voice_id: str = "shared_v",
    owner_id: str = "owner_x",
    name: str = "Some Voice",
    free_users_allowed: bool = True,
) -> MagicMock:
    voice = MagicMock()
    voice.voice_id = voice_id
    voice.public_owner_id = owner_id
    voice.name = name
    voice.free_users_allowed = free_users_allowed
    voice.preview_url = f"https://cdn.example.com/{voice_id}.mp3"
    voice.gender = "male"
    voice.age = "middle_aged"
    voice.accent = "british"
    return voice


def _client_with_shared(
    matches: list[MagicMock],
    added_voice_id: str = "added_v",
    library_match: MagicMock | None = None,
) -> MagicMock:
    client = MagicMock()
    client.voices.search.return_value = MagicMock(
        voices=[library_match] if library_match is not None else [],
    )
    client.voices.get_shared.return_value = MagicMock(voices=matches)
    client.voices.share.return_value = MagicMock(voice_id=added_voice_id)
    return client


class TestUpsert:
    """upsert prefers an existing workspace voice over a library lookup."""

    def test_returns_existing_voice_id_on_workspace_cache_hit(self) -> None:
        # Arrange
        cached = MagicMock()
        cached.name = "book:author:alice"
        cached.voice_id = "v_cached"
        client = _client_with_shared(matches=[], library_match=cached)
        provider = ElevenLabsLibraryCharacterProvider(
            client=client,
        )
        character = Character(
            id=2, name="Alice", gender="female", age="young", accent="british",
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "v_cached"
        client.voices.get_shared.assert_not_called()
        client.voices.share.assert_not_called()


class TestSharedLookup:
    """The shared-voices query carries the character's structured filters."""

    def test_queries_with_full_filters_and_adds_top_match(self) -> None:
        # Arrange
        match = _shared_voice(voice_id="sv1", owner_id="own1")
        client = _client_with_shared(matches=[match])
        provider = ElevenLabsLibraryCharacterProvider(
            client=client, book_language="en",
        )
        character = Character(
            id=3, name="Hagrid", gender="male", age="middle_aged",
            accent="british",
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "added_v"
        kwargs = client.voices.get_shared.call_args.kwargs
        assert kwargs["gender"] == "male"
        assert kwargs["age"] == "middle_aged"
        assert kwargs["accent"] == "british"
        assert kwargs["language"] == "en"
        client.voices.share.assert_called_once_with(
            "own1", "sv1", new_name="book:author:hagrid",
        )

    def test_skips_voices_not_allowed_for_free_users(self) -> None:
        # Arrange
        gated = _shared_voice(voice_id="gated", free_users_allowed=False)
        ok = _shared_voice(voice_id="ok", owner_id="own_ok")
        client = _client_with_shared(matches=[gated, ok])
        provider = ElevenLabsLibraryCharacterProvider(
            client=client,
        )
        character = Character(
            id=4, name="Pick", gender="female", age="young", accent="british",
        )

        # Act
        provider.upsert(character, _BOOK_ID)

        # Assert
        client.voices.share.assert_called_once_with(
            "own_ok", "ok", new_name="book:author:pick",
        )


class TestDedup:
    """Within a single run, two characters with the same query get different voices."""

    def test_second_character_gets_next_shared_voice_not_yet_assigned(self) -> None:
        # Arrange
        first = _shared_voice(voice_id="sv1", owner_id="own1", name="Voice One")
        second = _shared_voice(voice_id="sv2", owner_id="own2", name="Voice Two")
        client = MagicMock()
        client.voices.search.return_value = MagicMock(voices=[])
        client.voices.get_shared.return_value = MagicMock(voices=[first, second])
        client.voices.share.side_effect = [
            MagicMock(voice_id="added_1"),
            MagicMock(voice_id="added_2"),
        ]
        provider = ElevenLabsLibraryCharacterProvider(
            client=client,
        )
        char_a = Character(
            id=10, name="A", gender="male", age="middle_aged", accent="british",
        )
        char_b = Character(
            id=11, name="B", gender="male", age="middle_aged", accent="british",
        )

        # Act
        voice_a = provider.upsert(char_a, _BOOK_ID)
        voice_b = provider.upsert(char_b, _BOOK_ID)

        # Assert
        assert voice_a == "added_1"
        assert voice_b == "added_2"
        share_calls = client.voices.share.call_args_list
        assert share_calls[0].args[:2] == ("own1", "sv1")
        assert share_calls[1].args[:2] == ("own2", "sv2")


class TestRelaxation:
    """Relax filters in order when the strict query returns no voices."""

    def test_relaxes_accent_first(self) -> None:
        # Arrange
        match = _shared_voice(voice_id="v_relaxed")
        client = MagicMock()
        client.voices.search.return_value = MagicMock(voices=[])
        client.voices.get_shared.side_effect = [
            MagicMock(voices=[]),
            MagicMock(voices=[match]),
        ]
        client.voices.share.return_value = MagicMock(voice_id="added")
        provider = ElevenLabsLibraryCharacterProvider(
            client=client,
        )
        character = Character(
            id=5, name="X", gender="male", age="middle_aged", accent="british",
        )

        # Act
        voice_id = provider.upsert(character, _BOOK_ID)

        # Assert
        assert voice_id == "added"
        assert client.voices.get_shared.call_count == 2
        first_kwargs = client.voices.get_shared.call_args_list[0].kwargs
        second_kwargs = client.voices.get_shared.call_args_list[1].kwargs
        assert first_kwargs["accent"] == "british"
        assert "accent" not in second_kwargs
        assert second_kwargs["age"] == "middle_aged"

    def test_raises_when_every_relaxation_step_is_empty(self) -> None:
        # Arrange
        client = MagicMock()
        client.voices.search.return_value = MagicMock(voices=[])
        client.voices.get_shared.return_value = MagicMock(voices=[])
        provider = ElevenLabsLibraryCharacterProvider(
            client=client,
        )
        character = Character(
            id=6, name="Nope", gender="male", age="old", accent="martian",
        )

        # Act / Assert
        with pytest.raises(ValueError, match="No shared voice matched"):
            provider.upsert(character, _BOOK_ID)


class TestCandidates:
    """candidates shortlists voices instead of picking one."""

    def test_candidates_returns_up_to_limit(self) -> None:
        # Arrange
        voices = [_shared_voice(voice_id=f"sv{i}", owner_id=f"own{i}") for i in range(5)]
        client = _client_with_shared(matches=voices)
        provider = ElevenLabsLibraryCharacterProvider(client=client)
        character = Character(
            id=2, name="Alice", gender="female", age="young", accent="british",
        )

        # Act
        candidates = provider.candidates(character, limit=3)

        # Assert
        assert [c.voice_id for c in candidates] == ["sv0", "sv1", "sv2"]
        assert candidates[0].public_owner_id == "own0"
        assert candidates[0].preview_url == "https://cdn.example.com/sv0.mp3"

    def test_candidates_relaxes_filters_without_duplicates(self) -> None:
        # Arrange
        strict = _shared_voice(voice_id="strict", owner_id="own_s")
        relaxed = _shared_voice(voice_id="relaxed", owner_id="own_r")
        client = MagicMock()
        client.voices.search.return_value = MagicMock(voices=[])
        client.voices.get_shared.side_effect = [
            MagicMock(voices=[strict]),
            MagicMock(voices=[strict, relaxed]),
            MagicMock(voices=[strict, relaxed]),
        ]
        provider = ElevenLabsLibraryCharacterProvider(client=client)
        character = Character(
            id=3, name="Bob", gender="male", age="middle_aged", accent="russian",
        )

        # Act
        candidates = provider.candidates(character, limit=5)

        # Assert
        assert [c.voice_id for c in candidates] == ["strict", "relaxed"]
        accents = [
            call.kwargs.get("accent") for call in client.voices.get_shared.call_args_list
        ]
        assert accents == ["russian", None, None]

    def test_candidates_skips_paid_only_voices(self) -> None:
        # Arrange
        gated = _shared_voice(voice_id="gated", free_users_allowed=False)
        allowed = _shared_voice(voice_id="allowed", owner_id="own_ok")
        client = _client_with_shared(matches=[gated, allowed])
        provider = ElevenLabsLibraryCharacterProvider(client=client)
        character = Character(
            id=4, name="Cara", gender="female", age="young", accent="british",
        )

        # Act
        candidates = provider.candidates(character, limit=5)

        # Assert
        assert [c.voice_id for c in candidates] == ["allowed"]

    def test_candidates_empty_when_no_match(self) -> None:
        # Arrange
        client = _client_with_shared(matches=[])
        provider = ElevenLabsLibraryCharacterProvider(client=client)
        character = Character(
            id=5, name="Dan", gender="male", age="old", accent="american",
        )

        # Act
        candidates = provider.candidates(character, limit=5)

        # Assert
        assert candidates == []
