"""Tests for HTTPFileDownloader."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.downloader.http_file_downloader import HTTPFileDownloader

_URL = "https://cdn.example.com/preview.mp3"


def test_download_bytes_and_error() -> None:
    # Arrange
    ok_response = MagicMock()
    ok_response.content = b"audio-bytes"
    ok_response.raise_for_status.return_value = None
    downloader = HTTPFileDownloader()

    # Act
    with patch("src.downloader.http_file_downloader.requests.get", return_value=ok_response):
        downloaded = downloader.download_bytes(_URL)

    # Assert
    assert downloaded == b"audio-bytes"
    with patch(
        "src.downloader.http_file_downloader.requests.get",
        side_effect=requests.RequestException("boom"),
    ), pytest.raises(RuntimeError, match="Failed to download"):
        downloader.download_bytes(_URL)
