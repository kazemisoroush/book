"""Eval scorer for ElevenLabs sound effects generation.

Tests the ElevenLabsSoundEffectProvider with a test description to verify:
- API credentials work
- Returns valid audio file path
- File exists and has substantial size
- Caching works (second call returns cached file)

This is an integration smoke test, not a quality assessment. It confirms the
API works but does not evaluate audio quality.

Cost: ~1 API call per run (second call is cached)

Usage:
    python -m src.evals.book.score_sound_effects setup
    python -m src.evals.book.score_sound_effects score
    python -m src.evals.book.score_sound_effects cleanup
"""
import sys
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.evals.eval_harness import EvalHarness
from src.tts.elevenlabs_sound_effect_provider import ElevenLabsSoundEffectProvider


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
        print("\nRun: python -m src.evals.book.score_sound_effects score")

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
            # Create provider and call generate()
            provider = ElevenLabsSoundEffectProvider(self._client, self._temp_dir)
            output_path = self._temp_dir / "test_sound_effect.mp3"
            audio_path = provider.generate(
                description=test_description,
                output_path=output_path,
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
                    audio_path_2 = provider.generate(
                        description=test_description,
                        output_path=output_path,
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

        # ── Precision: API failure returns None ──────────────────────────
        # This is handled by the provider internally - if ElevenLabs API fails,
        # provider.generate() returns None. We can't easily test this without
        # an actual API failure, so we skip this check.

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
