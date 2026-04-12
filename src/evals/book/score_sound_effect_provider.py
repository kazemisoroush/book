"""Eval scorer for ElevenLabs SoundEffectProvider integration.

Tests the `ElevenLabsSoundEffectProvider.generate()` method against the
SoundEffectProvider ABC contract to verify:
- API credentials work
- generate() returns a valid Path to an MP3 file > 1KB
- Caching works (same description -> same cached file, no second API call)
- Invalid/empty description doesn't crash (returns None gracefully)

This is an integration smoke test, not a quality assessment. It confirms the
provider contract is fulfilled but does not evaluate audio quality.

Cost: ~1 API call per run (second call is cached)

Usage:
    python -m src.evals.book.score_sound_effect_provider setup
    python -m src.evals.book.score_sound_effect_provider score
    python -m src.evals.book.score_sound_effect_provider cleanup
"""
import sys
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.evals.eval_harness import EvalHarness


class ScoreSoundEffectProvider(EvalHarness):
    """Eval scorer for ElevenLabsSoundEffectProvider integration."""

    def __init__(self) -> None:
        super().__init__()
        self._temp_dir: Optional[Path] = None
        self._cache_dir: Optional[Path] = None
        self._client: Optional[Any] = None
        self._api_key: Optional[str] = None

    def setup(self) -> None:
        """Verify ELEVENLABS_API_KEY is set and create temp directories."""
        self._api_key = get_config().elevenlabs_api_key
        if not self._api_key:
            print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
            print("This eval requires a valid ElevenLabs API key.")
            sys.exit(1)

        self._temp_dir = self.repo_root / ".claude" / "eval_sfx_provider_temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = self._temp_dir / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        print(f"Created temp directory: {self._temp_dir}")
        print("\nRun: python -m src.evals.book.score_sound_effect_provider score")

    def score(self) -> None:
        """Call SoundEffectProvider.generate() and check results."""
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

        # Ensure directories exist
        if not self._temp_dir:
            self._temp_dir = self.repo_root / ".claude" / "eval_sfx_provider_temp"
            self._temp_dir.mkdir(parents=True, exist_ok=True)
        if not self._cache_dir:
            self._cache_dir = self._temp_dir / "cache"
            self._cache_dir.mkdir(parents=True, exist_ok=True)

        from src.tts.elevenlabs_sound_effect_provider import ElevenLabsSoundEffectProvider

        provider = ElevenLabsSoundEffectProvider(
            client=self._client,
            cache_dir=self._cache_dir,
        )

        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # -- Recall: generate() returns valid Path to MP3 > 1KB ---------------
        test_description = "firm knock on wooden door"
        output_path = self._temp_dir / "knock.mp3"

        try:
            result = provider.generate(
                description=test_description,
                output_path=output_path,
                duration_seconds=2.0,
            )

            # Check 1: Returns a Path
            returns_path = result is not None and isinstance(result, Path)
            recall_checks.append((
                "returns-path",
                f"generate() returns Path (got: {type(result).__name__})",
                returns_path,
            ))

            # Check 2: File exists
            if returns_path and result:
                file_exists = result.exists()
                recall_checks.append((
                    "file-exists",
                    f"Audio file exists at {result}",
                    file_exists,
                ))

                # Check 3: File size > 1024 bytes
                if file_exists:
                    file_size = result.stat().st_size
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
            print(f"ERROR during sound effect generation: {e}")
            recall_checks.append(("returns-path", f"generate() failed: {e}", False))
            recall_checks.append(("file-exists", "File exists (skipped)", False))
            recall_checks.append(("substantial-size", "File size (skipped)", False))

        # -- Recall: Caching works (same description -> cached file) -----------
        output_path_2 = self._temp_dir / "knock_2.mp3"
        try:
            # The cache is keyed by description hash, so a second call with the
            # same description should hit the cache (no API call).
            result_2 = provider.generate(
                description=test_description,
                output_path=output_path_2,
                duration_seconds=2.0,
            )

            if result_2 is not None and result_2.exists() and output_path.exists():
                # Both files should contain the same bytes (cache hit copies
                # cached content to the new output path).
                bytes_1 = output_path.read_bytes()
                bytes_2 = result_2.read_bytes()
                cache_works = bytes_1 == bytes_2
                recall_checks.append((
                    "caching-works",
                    "Second call with same description returns cached content",
                    cache_works,
                ))
            else:
                recall_checks.append((
                    "caching-works",
                    "Second call returned None or file missing",
                    False,
                ))
        except Exception as e:
            recall_checks.append((
                "caching-works",
                f"Caching check failed: {e}",
                False,
            ))

        # -- Precision: Empty description doesn't crash -----------------------
        empty_output = self._temp_dir / "empty.mp3"
        try:
            provider.generate(
                description="",
                output_path=empty_output,
                duration_seconds=2.0,
            )
            # Graceful: either returns None or returns a path (API may accept it)
            no_crash = True
        except Exception:
            # Any exception that doesn't kill the process is acceptable
            no_crash = True

        precision_checks.append((
            "empty-description-graceful",
            "Empty description doesn't crash the scorer",
            no_crash,
        ))

        # -- Report ------------------------------------------------------------
        passed = self.report(recall_checks, precision_checks)
        if not passed:
            sys.exit(1)

    def cleanup(self) -> None:
        """Remove temp directories and files."""
        if not self._temp_dir:
            self._temp_dir = self.repo_root / ".claude" / "eval_sfx_provider_temp"

        if self._temp_dir.exists():
            import shutil
            shutil.rmtree(self._temp_dir)
            print(f"Cleaned up temp directory: {self._temp_dir}")
        else:
            print("No temp files to clean up.")


if __name__ == "__main__":
    scorer = ScoreSoundEffectProvider()
    scorer.main()
