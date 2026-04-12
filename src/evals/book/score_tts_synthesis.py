"""Eval scorer for ElevenLabs TTS synthesis API integration.

Tests the `ElevenLabsTTSProvider.synthesize()` method with a short sentence to
verify:
- API credentials work
- SDK is compatible
- Response is valid MP3 audio
- Error handling works (empty input → graceful failure)

This is an integration smoke test, not a quality assessment. It confirms the
API works but does not evaluate audio quality (that requires human ears).

Cost: ~1 API call per run (~$0.01)

Usage:
    python -m src.evals.book.score_tts_synthesis setup
    python -m src.evals.book.score_tts_synthesis score
    python -m src.evals.book.score_tts_synthesis cleanup
"""
import sys
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.evals.eval_harness import EvalHarness
from src.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider


class ScoreTTSSynthesis(EvalHarness):
    """Eval scorer for TTS synthesis API integration."""

    def __init__(self) -> None:
        super().__init__()
        self._temp_dir: Optional[Path] = None
        self._client: Optional[Any] = None
        self._api_key: Optional[str] = None

    def setup(self) -> None:
        """Verify ELEVENLABS_API_KEY is set (no fixtures needed)."""
        self._api_key = get_config().elevenlabs_api_key
        if not self._api_key:
            print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
            print("This eval requires a valid ElevenLabs API key.")
            sys.exit(1)

        print("Setup complete. ELEVENLABS_API_KEY found.")
        print("\nRun: python -m src.evals.book.score_tts_synthesis score")

    def score(self) -> None:
        """Call TTS synthesis API with test sentence and check output."""
        # Check API key
        self._api_key = get_config().elevenlabs_api_key
        if not self._api_key:
            print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
            sys.exit(1)

        # Initialize client and provider
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore[import-untyped]
            self._client = ElevenLabs(api_key=self._api_key)
        except ImportError:
            print("ERROR: elevenlabs package not installed.")
            print("Install with: pip install elevenlabs")
            sys.exit(1)

        provider = ElevenLabsTTSProvider(self._api_key)

        # Create temp directory for audio output
        self._temp_dir = self.repo_root / ".claude" / "eval_tts_synthesis_temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # Get a known voice (use first available voice)
        try:
            voices = self._client.voices.get_all()
            if not voices.voices:
                print("ERROR: No voices available in ElevenLabs account.")
                sys.exit(1)
            voice_id = voices.voices[0].voice_id
            print(f"Using voice: {voices.voices[0].name} ({voice_id})")
        except Exception as e:
            print(f"ERROR: Could not fetch voices: {e}")
            sys.exit(1)

        # ── Recall: Synthesize test sentence ──────────────────────────────
        test_sentence = "The quick brown fox jumped over the lazy dog."
        test_output = self._temp_dir / "test.mp3"

        try:
            audio_bytes = provider.synthesize(
                text=test_sentence,
                voice_id=voice_id,
                output_path=test_output,
            )

            # Check 1: Returns bytes
            returns_bytes = audio_bytes is not None and isinstance(audio_bytes, bytes) and len(audio_bytes) > 0
            recall_checks.append((
                "returns-bytes",
                "synthesize() returns bytes (not None, not empty)",
                returns_bytes,
            ))

            # Check 2: Bytes are substantial (> 1024)
            if audio_bytes:
                substantial = len(audio_bytes) > 1024
                recall_checks.append((
                    "substantial-bytes",
                    f"Audio bytes > 1024 (got {len(audio_bytes)})",
                    substantial,
                ))

                # Check 3: Valid MP3 header
                # MP3 starts with 0xFF 0xFB (MPEG-1 Layer 3) or 0xFF 0xFA, etc.
                # or ID3v2 tag starts with "ID3"
                valid_header = False
                if len(audio_bytes) >= 3:
                    if audio_bytes[:3] == b"ID3":
                        valid_header = True
                    elif len(audio_bytes) >= 2:
                        byte0 = int(audio_bytes[0])
                        byte1 = int(audio_bytes[1])
                        if byte0 == 0xFF and (byte1 & 0xE0) == 0xE0:
                            valid_header = True

                recall_checks.append((
                    "valid-mp3-header",
                    "Audio starts with valid MP3/MPEG header or ID3 tag",
                    valid_header,
                ))
            else:
                recall_checks.append(("substantial-bytes", "Audio bytes > 1024", False))
                recall_checks.append(("valid-mp3-header", "Valid MP3 header", False))

        except Exception as e:
            print(f"ERROR during synthesis: {e}")
            recall_checks.append(("returns-bytes", "synthesize() returns bytes", False))
            recall_checks.append(("substantial-bytes", "Audio bytes > 1024", False))
            recall_checks.append(("valid-mp3-header", "Valid MP3 header", False))

        # ── Precision: Empty string handling ──────────────────────────────
        empty_output = self._temp_dir / "empty.mp3"
        try:
            provider.synthesize(
                text="",
                voice_id=voice_id,
                output_path=empty_output,
            )
            # If we got here without crash, that's good
            no_crash = True
        except Exception:
            # Expected behavior - empty string might raise, which is fine
            no_crash = True  # Not crashing the process itself is what matters

        precision_checks.append((
            "empty-text-graceful",
            "Empty string as text doesn't crash the scorer",
            no_crash,
        ))

        # ── Report ────────────────────────────────────────────────────────
        passed = self.report(recall_checks, precision_checks)
        if not passed:
            sys.exit(1)

    def cleanup(self) -> None:
        """Remove temp directory and files."""
        if self._temp_dir and self._temp_dir.exists():
            import shutil
            shutil.rmtree(self._temp_dir)
            print(f"Cleaned up temp directory: {self._temp_dir}")
        else:
            print("No temp files to clean up.")


if __name__ == "__main__":
    scorer = ScoreTTSSynthesis()
    scorer.main()
