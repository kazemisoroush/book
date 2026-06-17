"""Unit tests for AudioStore (object-based interface)."""
import json
from pathlib import Path

from src.storage.audio_store import AudioStore
from src.storage.local_storage import LocalStorage
from src.storage.objects import (
    APIRequest,
    MixOutputRef,
    SFXBeat,
    SFXBeatRef,
    SilenceClipRef,
    TrimStepRef,
    TTSBeat,
    TTSBeatRef,
    TTSChunk,
    VoiceRequestRef,
)


def _store(tmp_path: Path) -> AudioStore:
    return AudioStore(LocalStorage(tmp_path))


class TestTTSBeat:
    """save_tts_beat / has_tts_beat round-trip a per-beat artifact."""

    def test_save_then_has(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        beat = TTSBeat(
            book_id="alice", provider="elevenlabs_v2", index=7, audio=b"audio",
        )

        # Act
        store.save_tts_beat(beat)

        # Assert
        assert store.has_tts_beat(beat.ref) is True
        on_disk = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_v2" / "beat_0007.mp3"
        assert on_disk.read_bytes() == b"audio"

    def test_has_returns_false_for_missing(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)

        # Act / Assert
        assert store.has_tts_beat(TTSBeatRef("alice", "elevenlabs_v2", 1)) is False

    def test_save_writes_api_request_sidecar(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        beat = TTSBeat(
            book_id="alice", provider="fish_audio", index=2, audio=b"x",
        )
        api_request = APIRequest(
            method="POST",
            url="https://api.example.com/tts",
            headers={"xi-api-key": "sk-secret", "Content-Type": "application/json"},
            body={"text": "hi"},
        )

        # Act
        store.save_tts_beat(beat, api_request=api_request)

        # Assert
        sidecar = (
            tmp_path / "alice" / "audio" / "tts" / "fish_audio" / "beat_0002.request.json"
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["method"] == "POST"
        assert payload["headers"]["xi-api-key"] == "***"
        assert payload["body"] == {"text": "hi"}


class TestTTSChunk:
    """Dialogue chunks save and list in index order."""

    def test_save_then_list(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        store.save_tts_chunk(TTSChunk("alice", "elevenlabs_dialogue", "chapter_001", 2, b"x"))
        store.save_tts_chunk(TTSChunk("alice", "elevenlabs_dialogue", "chapter_001", 1, b"y"))

        # Act
        refs = store.list_tts_chunks("alice", "elevenlabs_dialogue", "chapter_001")

        # Assert
        assert [r.index for r in refs] == [1, 2]


class TestSFXBeat:
    """SFX beats save with mp3 or wav extension."""

    def test_save_mp3(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        beat = SFXBeat(
            book_id="alice", provider="elevenlabs", index=1, audio=b"sfx",
        )

        # Act
        store.save_sfx_beat(beat)

        # Assert
        on_disk = tmp_path / "alice" / "audio" / "sfx" / "elevenlabs" / "beat_0001.mp3"
        assert on_disk.read_bytes() == b"sfx"

    def test_open_for_writing_wav(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        ref = SFXBeatRef("alice", "audiogen", 3, extension="wav")

        # Act
        with store.open_sfx_beat(ref, "w") as path:
            path.write_bytes(b"wav-bytes")

        # Assert
        assert store.has_sfx_beat(ref) is True
        on_disk = tmp_path / "alice" / "audio" / "sfx" / "audiogen" / "beat_0003.wav"
        assert on_disk.read_bytes() == b"wav-bytes"


class TestSilenceClip:
    """Silence clips are keyed by duration_ms."""

    def test_open_for_writing(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        ref = SilenceClipRef("alice", "elevenlabs_v2", 1000)

        # Act
        with store.open_silence_clip(ref, "w") as path:
            path.write_bytes(b"silence")

        # Assert
        assert store.has_silence_clip(ref) is True


class TestMixOutput:
    """Mix outputs land under audio/mix/<provider>/<slug>.mp3."""

    def test_open_for_writing(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        ref = MixOutputRef("alice", "fish_audio", "chapter_001")

        # Act
        with store.open_mix_output(ref, "w") as path:
            path.write_bytes(b"mix")

        # Assert
        on_disk = tmp_path / "alice" / "audio" / "mix" / "fish_audio" / "chapter_001.mp3"
        assert on_disk.read_bytes() == b"mix"


class TestTrimSteps:
    """Trim intermediates and final trimmed siblings live next to the source beat."""

    def test_write_and_read_intermediate(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        beat_ref = TTSBeatRef("alice", "elevenlabs_v2", 1)
        intermediate = TrimStepRef(beat=beat_ref, step=0)

        # Act
        with store.open_trim_step(intermediate, "w") as path:
            path.write_bytes(b"intermediate")
        with store.open_trim_step(intermediate, "r") as path:
            data = path.read_bytes()

        # Assert
        assert data == b"intermediate"

    def test_final_trimmed_sibling_distinct_from_intermediate(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        beat_ref = TTSBeatRef("alice", "elevenlabs_v2", 1)

        # Act
        with store.open_trim_step(TrimStepRef(beat=beat_ref, step=0), "w") as path:
            path.write_bytes(b"step")
        with store.open_trim_step(TrimStepRef(beat=beat_ref, step="final"), "w") as path:
            path.write_bytes(b"final")

        # Assert
        with store.open_final_trimmed_beat(beat_ref) as final_path:
            assert final_path.read_bytes() == b"final"

    def test_delete_trim_artifacts_removes_steps_and_final(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        beat_ref = TTSBeatRef("alice", "elevenlabs_v2", 1)
        store.save_tts_beat(TTSBeat("alice", "elevenlabs_v2", 1, b"raw"))
        with store.open_trim_step(TrimStepRef(beat=beat_ref, step=0), "w") as p:
            p.write_bytes(b"step0")
        with store.open_trim_step(TrimStepRef(beat=beat_ref, step="final"), "w") as p:
            p.write_bytes(b"final")

        # Act
        store.delete_trim_artifacts(beat_ref)

        # Assert
        assert store.has_tts_beat(beat_ref) is True
        beat_dir = tmp_path / "alice" / "audio" / "tts" / "elevenlabs_v2"
        leftover = sorted(p.name for p in beat_dir.glob("*"))
        assert leftover == ["beat_0001.mp3"]


class TestConcatManifest:
    """with_concat_manifest writes, yields, and deletes one ffmpeg concat file."""

    def test_writes_and_cleans_up(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        ref = MixOutputRef("alice", "fish_audio", "chapter_001")

        # Act
        with store.with_concat_manifest(ref, ["file 'one.mp3'", "file 'two.mp3'"]) as path:
            assert path.exists()
            assert path.read_text() == "file 'one.mp3'\nfile 'two.mp3'\n"

        # Assert
        assert not path.exists()


class TestVoiceRequests:
    """Voice and shared-voice API request artifacts."""

    def test_save_voice_request(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        request = APIRequest(
            method="GET",
            url="https://api.example.com/voices",
            headers={"xi-api-key": "secret"},
            body=None,
        )

        # Act
        store.save_voice_request(
            VoiceRequestRef("alice", "elizabeth_bennet", "library_search"),
            request,
        )

        # Assert
        sidecar = (
            tmp_path / "alice" / "voices" / "elizabeth_bennet" / "library_search.request.json"
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["url"] == "https://api.example.com/voices"
        assert payload["headers"]["xi-api-key"] == "***"

    def test_save_shared_voice_search(self, tmp_path: Path) -> None:
        # Arrange
        store = _store(tmp_path)
        request = APIRequest(
            method="GET",
            url="https://api.example.com/shared",
            headers={},
            body={"page_size": 100},
        )

        # Act
        store.save_shared_voice_search(request)

        # Assert
        sidecar = tmp_path / "_shared_voices" / "shared_search.request.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["body"] == {"page_size": 100}
