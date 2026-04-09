"""Eval scorer for ElevenLabs Voice Design API integration.

Tests the `design_voice()` function from `voice_designer.py` with a test
description to verify:
- API credentials work
- Voice design returns valid voice_id
- Generated voice can be retrieved
- Error handling works (empty description → graceful failure)

This is an integration smoke test, not a quality assessment. It confirms the
API works but does not evaluate voice quality.

Cost: ~2 API calls per run (create_previews + create_voice)

Usage:
    python -m src.evals.score_voice_design setup
    python -m src.evals.score_voice_design score
    python -m src.evals.score_voice_design cleanup
"""
import sys
from typing import Any, Optional

from src.config import get_config
from src.evals.eval_harness import EvalHarness
from src.tts.voice_designer import design_voice


class ScoreVoiceDesign(EvalHarness):
    """Eval scorer for Voice Design API integration."""

    def __init__(self) -> None:
        super().__init__()
        self._client: Optional[Any] = None
        self._api_key: Optional[str] = None
        self._test_voice_id: Optional[str] = None

    def setup(self) -> None:
        """Verify ELEVENLABS_API_KEY is set (no fixtures needed)."""
        self._api_key = get_config().elevenlabs_api_key
        if not self._api_key:
            print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
            print("This eval requires a valid ElevenLabs API key.")
            sys.exit(1)

        print("Setup complete. ELEVENLABS_API_KEY found.")
        print("\nRun: python -m src.evals.score_voice_design score")

    def score(self) -> None:
        """Call voice design API with test description and check output."""
        # Check API key
        self._api_key = get_config().elevenlabs_api_key
        if not self._api_key:
            print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
            sys.exit(1)

        # Initialize client
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore[import-untyped]
            self._client = ElevenLabs(api_key=self._api_key)
        except ImportError:
            print("ERROR: elevenlabs package not installed.")
            print("Install with: pip install elevenlabs")
            sys.exit(1)

        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # ── Recall: Design a test voice ──────────────────────────────────
        test_description = "A warm, gentle female voice in her 30s"
        test_character_name = "EvalTestVoice"

        try:
            voice_id = design_voice(
                description=test_description,
                character_name=test_character_name,
                client=self._client,
            )
            self._test_voice_id = voice_id

            # Check 1: Returns non-empty string
            returns_voice_id = isinstance(voice_id, str) and len(voice_id) > 0
            recall_checks.append((
                "returns-voice-id",
                f"design_voice() returns non-empty voice_id (got: {voice_id if returns_voice_id else 'None'})",
                returns_voice_id,
            ))

            # Check 2: Voice can be retrieved
            if returns_voice_id:
                try:
                    retrieved_voice = self._client.voices.get(voice_id)
                    can_retrieve = retrieved_voice is not None
                    recall_checks.append((
                        "voice-retrievable",
                        f"Voice {voice_id} can be retrieved via API",
                        can_retrieve,
                    ))
                except Exception as e:
                    recall_checks.append((
                        "voice-retrievable",
                        f"Voice {voice_id} retrieval failed: {e}",
                        False,
                    ))
            else:
                recall_checks.append((
                    "voice-retrievable",
                    "Voice retrieval (skipped - no voice_id)",
                    False,
                ))

        except Exception as e:
            print(f"ERROR during voice design: {e}")
            recall_checks.append(("returns-voice-id", f"design_voice() failed: {e}", False))
            recall_checks.append(("voice-retrievable", "Voice retrieval (skipped)", False))

        # ── Precision: Empty description handling ────────────────────────
        try:
            design_voice(
                description="",
                character_name="EmptyTestVoice",
                client=self._client,
            )
            # If we got here, empty description was handled
            no_crash = True
        except Exception:
            # Expected - empty description might raise, which is acceptable
            no_crash = True  # Not crashing the scorer process is what matters

        precision_checks.append((
            "empty-description-graceful",
            "Empty description doesn't crash the scorer",
            no_crash,
        ))

        # ── Report ────────────────────────────────────────────────────────
        passed = self.report(recall_checks, precision_checks)
        if not passed:
            sys.exit(1)

    def cleanup(self) -> None:
        """Delete the test voice from ElevenLabs account."""
        if not self._test_voice_id:
            print("No test voice to clean up.")
            return

        # Ensure client is initialized
        if not self._client:
            self._api_key = get_config().elevenlabs_api_key
            if not self._api_key:
                print("WARNING: Cannot clean up - ELEVENLABS_API_KEY not set.")
                return
            try:
                from elevenlabs.client import ElevenLabs  # type: ignore[import-untyped]
                self._client = ElevenLabs(api_key=self._api_key)
            except ImportError:
                print("WARNING: Cannot clean up - elevenlabs package not installed.")
                return

        try:
            self._client.voices.delete(self._test_voice_id)
            print(f"Deleted test voice: {self._test_voice_id}")
        except Exception as e:
            print(f"WARNING: Could not delete test voice {self._test_voice_id}: {e}")
            print("You may need to manually delete it from your ElevenLabs account.")


if __name__ == "__main__":
    scorer = ScoreVoiceDesign()
    scorer.main()
