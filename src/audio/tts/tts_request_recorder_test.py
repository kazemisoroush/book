"""Tests for write_tts_request."""
import json
from pathlib import Path

from src.audio.tts.tts_request_recorder import write_tts_request


class TestWriteTtsRequestFile:
    """write_tts_request writes a sibling .request.json next to the audio path."""

    def test_writes_sibling_request_json(self, tmp_path: Path) -> None:
        # Arrange
        audio_path = tmp_path / "audio" / "beat_0001.mp3"

        # Act
        write_tts_request(
            output_path=audio_path,
            method="POST",
            url="https://api.example.com/tts",
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
            body={"text": "Hello.", "voice_id": "vid"},
        )

        # Assert
        request_path = audio_path.with_suffix(".request.json")
        assert request_path.is_file()
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert payload["method"] == "POST"
        assert payload["url"] == "https://api.example.com/tts"
        assert payload["headers"]["Authorization"] == "Bearer ***"
        assert payload["headers"]["Content-Type"] == "application/json"
        assert payload["body"] == {"text": "Hello.", "voice_id": "vid"}


class TestWriteTtsRequestCurlField:
    """The curl field is a copy-pasteable command line."""

    def test_curl_includes_method_url_headers_and_data(self, tmp_path: Path) -> None:
        # Arrange
        audio_path = tmp_path / "beat_0001.mp3"

        # Act
        write_tts_request(
            output_path=audio_path,
            method="post",
            url="https://api.example.com/tts",
            headers={"Authorization": "Bearer secret"},
            body={"text": "Hello."},
        )

        # Assert
        payload = json.loads(audio_path.with_suffix(".request.json").read_text(encoding="utf-8"))
        curl = payload["curl"]
        assert curl.startswith("curl -X POST ")
        assert "https://api.example.com/tts" in curl
        assert "Authorization: Bearer ***" in curl
        assert '"text": "Hello."' in curl


class TestWriteTtsRequestNoBody:
    """body=None is omitted from the curl --data argument."""

    def test_no_data_when_body_is_none(self, tmp_path: Path) -> None:
        # Arrange
        audio_path = tmp_path / "beat_0001.mp3"

        # Act
        write_tts_request(
            output_path=audio_path,
            method="GET",
            url="https://api.example.com/voices",
            headers={"Authorization": "Bearer secret"},
            body=None,
        )

        # Assert
        payload = json.loads(audio_path.with_suffix(".request.json").read_text(encoding="utf-8"))
        assert "--data" not in payload["curl"]
        assert payload["body"] is None


class TestWriteTtsRequestRedaction:
    """Credential headers are redacted; non-credential headers pass through."""

    def test_case_insensitive_authorization_is_redacted(self, tmp_path: Path) -> None:
        # Arrange
        audio_path = tmp_path / "beat_0001.mp3"

        # Act
        write_tts_request(
            output_path=audio_path,
            method="POST",
            url="https://api.example.com/tts",
            headers={"authorization": "Bearer secret-value", "X-Trace": "abc"},
            body=None,
        )

        # Assert
        payload = json.loads(audio_path.with_suffix(".request.json").read_text(encoding="utf-8"))
        assert payload["headers"]["authorization"] == "Bearer ***"
        assert payload["headers"]["X-Trace"] == "abc"

    def test_xi_api_key_is_redacted(self, tmp_path: Path) -> None:
        # Arrange
        audio_path = tmp_path / "beat_0002.mp3"

        # Act
        write_tts_request(
            output_path=audio_path,
            method="POST",
            url="https://api.elevenlabs.io/v1/text-to-speech/vid",
            headers={"xi-api-key": "sk-secret", "Content-Type": "application/json"},
            body={"text": "Hi."},
        )

        # Assert
        payload = json.loads(audio_path.with_suffix(".request.json").read_text(encoding="utf-8"))
        assert payload["headers"]["xi-api-key"] == "***"
        assert payload["headers"]["Content-Type"] == "application/json"
