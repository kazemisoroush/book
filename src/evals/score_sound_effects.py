"""Eval scorer for ElevenLabs sound effects generation.

Tests the `get_sound_effect()` function from `sound_effects_generator.py` with
a test description to verify:
- API credentials work
- Returns valid audio file path
- File exists and has substantial size
- Caching works (second call returns cached file)
- Error handling works (client=None → returns None)

This is an integration smoke test, not a quality assessment. It confirms the
API works but does not evaluate audio quality.

Cost: ~1 API call per run (second call is cached)

Usage:
    python -m src.evals.score_sound_effects setup
    python -m src.evals.score_sound_effects score
    python -m src.evals.score_sound_effects cleanup
"""
import sys
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.evals.eval_harness import EvalHarness
from src.tts.sound_effects_generator import get_sound_effect


class ScoreSoundEffects(EvalHarness):
    """Eval scorer for sound effects generation."""

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

        self._temp_dir = self.repo_root / ".claude" / "eval_sound_effects_temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        print(f"Created temp directory: {self._temp_dir}")
        print("\nRun: python -m src.evals.score_sound_effects score")

    def score(self) -> None:
        """Call sound effects API with test description and check output."""
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
            self._temp_dir = self.repo_root / ".claude" / "eval_sound_effects_temp"
            self._temp_dir.mkdir(parents=True, exist_ok=True)

        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # ── Recall: Generate sound effect ────────────────────────────────
        test_description = "firm knock on wooden door"

        try:
            audio_path = get_sound_effect(
                description=test_description,
                output_dir=self._temp_dir,
                client=self._client,
                duration_seconds=2.0,
            )

            # Check 1: Returns a Path
            returns_path = audio_path is not None and isinstance(audio_path, Path)
            recall_checks.append((
                "returns-path",
                f"get_sound_effect() returns Path (got: {type(audio_path).__name__})",
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

                # Check 4: Second call returns cached file (no new API call)
                if file_exists:
                    # Get modification time of first file
                    first_mtime = audio_path.stat().st_mtime

                    # Call again with same description
                    audio_path_2 = get_sound_effect(
                        description=test_description,
                        output_dir=self._temp_dir,
                        client=self._client,
                        duration_seconds=2.0,
                    )

                    if audio_path_2 and audio_path_2.exists():
                        second_mtime = audio_path_2.stat().st_mtime
                        is_cached = (audio_path == audio_path_2) and (first_mtime == second_mtime)
                        recall_checks.append((
                            "caching-works",
                            "Second call with same description returns cached file",
                            is_cached,
                        ))
                    else:
                        recall_checks.append((
                            "caching-works",
                            "Second call returned None or file missing",
                            False,
                        ))
                else:
                    recall_checks.append((
                        "caching-works",
                        "Caching (skipped - first file doesn't exist)",
                        False,
                    ))
            else:
                recall_checks.append(("file-exists", "File exists (skipped)", False))
                recall_checks.append(("substantial-size", "File size (skipped)", False))
                recall_checks.append(("caching-works", "Caching (skipped)", False))

        except Exception as e:
            print(f"ERROR during sound effect generation: {e}")
            recall_checks.append(("returns-path", f"get_sound_effect() failed: {e}", False))
            recall_checks.append(("file-exists", "File exists (skipped)", False))
            recall_checks.append(("substantial-size", "File size (skipped)", False))
            recall_checks.append(("caching-works", "Caching (skipped)", False))

        # ── Precision: client=None returns None ───────────────────────────
        try:
            result = get_sound_effect(
                description="test sound",
                output_dir=self._temp_dir,
                client=None,  # No client provided
            )
            returns_none = result is None
            precision_checks.append((
                "none-when-no-client",
                "client=None returns None (graceful skip)",
                returns_none,
            ))
        except Exception as e:
            precision_checks.append((
                "none-when-no-client",
                f"client=None raised: {e}",
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
    scorer = ScoreSoundEffects()
    scorer.main()
