"""Convenience runner for all TTS eval scorers.

Runs all ElevenLabs TTS eval scorers in sequence and reports combined
pass/fail. This is the recommended way to smoke-test the entire ElevenLabs
integration after SDK upgrades or API changes.

The provider contract eval is deterministic (no API calls) and always runs
first. The remaining scorers require ELEVENLABS_API_KEY.

Cost: ~7 API calls per run (~$0.05-0.15)

Usage:
    python -m src.evals.run_tts_evals
"""
import sys

from src.config import get_config
from src.evals.eval_harness import EvalHarness
from src.evals.score_ambient_audio import ScoreAmbientAudio
from src.evals.score_ambient_provider import ScoreAmbientProvider
from src.evals.score_provider_contract import ScoreProviderContract
from src.evals.score_sound_effect_provider import ScoreSoundEffectProvider
from src.evals.score_sound_effects import ScoreSoundEffects
from src.evals.score_tts_synthesis import ScoreTTSSynthesis
from src.evals.score_voice_design import ScoreVoiceDesign


def _run_scorer(
    name: str, scorer: EvalHarness, results: list[tuple[str, bool]],
) -> None:
    """Run a single scorer through setup/score/cleanup and record result."""
    print(f"\n{'─' * 60}")
    print(f"Running: {name}")
    print(f"{'─' * 60}")

    try:
        scorer.setup()

        try:
            scorer.score()
            results.append((name, True))
            print(f"\n{name}: PASS")
        except SystemExit as e:
            if e.code == 1:
                results.append((name, False))
                print(f"\n{name}: FAIL")
            else:
                raise

        scorer.cleanup()

    except Exception as e:
        print(f"\nERROR in {name}: {e}")
        results.append((name, False))


def main() -> None:
    """Run all TTS eval scorers and report combined results."""
    print("=" * 60)
    print("TTS EVAL SUITE")
    print("=" * 60)

    results: list[tuple[str, bool]] = []

    # Phase 1: Deterministic evals (no API key needed, free)
    print("\n--- Phase 1: Deterministic contract checks (free) ---")
    free_scorers: list[tuple[str, EvalHarness]] = [
        ("Provider Contract", ScoreProviderContract()),
    ]

    for name, scorer in free_scorers:
        _run_scorer(name, scorer, results)

    # Phase 2: API integration evals (require ELEVENLABS_API_KEY)
    config = get_config()
    if not config.elevenlabs_api_key:
        print("\nWARNING: ELEVENLABS_API_KEY not set. Skipping API integration evals.")
        print("Only deterministic evals were run.\n")
    else:
        print("\n--- Phase 2: API integration evals (requires ELEVENLABS_API_KEY) ---")
        api_scorers: list[tuple[str, EvalHarness]] = [
            ("TTS Synthesis", ScoreTTSSynthesis()),
            ("Voice Design", ScoreVoiceDesign()),
            ("Ambient Audio", ScoreAmbientAudio()),
            ("Sound Effects", ScoreSoundEffects()),
            ("SoundEffect Provider", ScoreSoundEffectProvider()),
            ("Ambient Provider", ScoreAmbientProvider()),
        ]

        for name, scorer in api_scorers:
            _run_scorer(name, scorer, results)

    # Summary
    print("\n" + "=" * 60)
    print("TTS EVAL SUITE RESULTS")
    print("=" * 60)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    print(f"\nTotal: {passed_count}/{total_count} scorers passed")

    if passed_count == total_count:
        print("\nScore: PASS")
        sys.exit(0)
    else:
        print("\nScore: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
