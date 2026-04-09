"""Eval scorer for ElevenLabs ambient audio generation.

Tests the `get_ambient_audio()` function from `ambient_generator.py` with a
test Scene to verify:
- API credentials work
- Returns valid audio file path
- File exists and has substantial size
- Error handling works (ambient_prompt=None → returns None)

This is an integration smoke test, not a quality assessment. It confirms the
API works but does not evaluate audio quality.

Cost: ~1 API call per run

Usage:
    python -m src.evals.score_ambient_audio setup
    python -m src.evals.score_ambient_audio score
    python -m src.evals.score_ambient_audio cleanup
"""
import sys
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.domain.models import Scene
from src.evals.eval_harness import EvalHarness
from src.tts.ambient_generator import get_ambient_audio


class ScoreAmbientAudio(EvalHarness):
    """Eval scorer for ambient audio generation."""

    def __init__(self) -> None:
        super().__init__()
        self._temp_dir: Optional[Path] = None
        self._client: Optional[Any] = None
        self._api_key: Optional[str] = None

    def setup(self) -> None:
        """Create temp output directory."""
        self._api_key = get_config().elevenlabs_api_key
        if not self._api_key:
            print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
            print("This eval requires a valid ElevenLabs API key.")
            sys.exit(1)

        self._temp_dir = self.repo_root / ".claude" / "eval_ambient_audio_temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        print(f"Created temp directory: {self._temp_dir}")
        print("\nRun: python -m src.evals.score_ambient_audio score")

    def score(self) -> None:
        """Call ambient audio API with test Scene and check output."""
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

        # Ensure temp dir exists
        if not self._temp_dir:
            self._temp_dir = self.repo_root / ".claude" / "eval_ambient_audio_temp"
            self._temp_dir.mkdir(parents=True, exist_ok=True)

        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # ── Recall: Generate ambient audio for test scene ────────────────
        test_scene = Scene(
            scene_id="test_library",
            environment="A quiet library with occasional page turns",
            acoustic_hints=["soft", "hushed", "paper rustling"],
            ambient_prompt="quiet library with occasional page turns",
            ambient_volume=-20.0,
        )

        try:
            audio_path = get_ambient_audio(
                scene=test_scene,
                output_dir=self._temp_dir,
                client=self._client,
                duration_seconds=5.0,  # Short duration to save credits
            )

            # Check 1: Returns a Path
            returns_path = audio_path is not None and isinstance(audio_path, Path)
            recall_checks.append((
                "returns-path",
                f"get_ambient_audio() returns Path (got: {type(audio_path).__name__})",
                returns_path,
            ))

            # Check 2: File exists
            if returns_path and audio_path:
                file_exists = audio_path.exists()
                recall_checks.append((
                    "file-exists",
                    f"Audio file exists at {audio_path}",
                    file_exists,
                ))

                # Check 3: File size > 1024 bytes
                if file_exists:
                    file_size = audio_path.stat().st_size
                    substantial = file_size > 1024
                    recall_checks.append((
                        "substantial-size",
                        f"Audio file > 1024 bytes (got {file_size})",
                        substantial,
                    ))
                else:
                    recall_checks.append((
                        "substantial-size",
                        "Audio file size (skipped - file doesn't exist)",
                        False,
                    ))
            else:
                recall_checks.append(("file-exists", "File exists (skipped)", False))
                recall_checks.append(("substantial-size", "File size (skipped)", False))

        except Exception as e:
            print(f"ERROR during ambient generation: {e}")
            recall_checks.append(("returns-path", f"get_ambient_audio() failed: {e}", False))
            recall_checks.append(("file-exists", "File exists (skipped)", False))
            recall_checks.append(("substantial-size", "File size (skipped)", False))

        # ── Precision: Scene with ambient_prompt=None returns None ────────
        scene_no_ambient = Scene(
            scene_id="test_no_ambient",
            environment="Silent room",
            acoustic_hints=["dead quiet"],
            ambient_prompt=None,  # No ambient requested
            ambient_volume=-20.0,
        )

        try:
            result = get_ambient_audio(
                scene=scene_no_ambient,
                output_dir=self._temp_dir,
                client=self._client,
            )
            returns_none = result is None
            precision_checks.append((
                "none-when-no-prompt",
                "Scene with ambient_prompt=None returns None (no API call)",
                returns_none,
            ))
        except Exception as e:
            precision_checks.append((
                "none-when-no-prompt",
                f"Scene with ambient_prompt=None raised: {e}",
                False,
            ))

        # ── Report ────────────────────────────────────────────────────────
        passed = self.report(recall_checks, precision_checks)
        if not passed:
            sys.exit(1)

    def cleanup(self) -> None:
        """Remove temp output directory."""
        if self._temp_dir and self._temp_dir.exists():
            import shutil
            shutil.rmtree(self._temp_dir)
            print(f"Cleaned up temp directory: {self._temp_dir}")
        else:
            print("No temp files to clean up.")


if __name__ == "__main__":
    scorer = ScoreAmbientAudio()
    scorer.main()
