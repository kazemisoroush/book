"""Convenience runner for all TTS eval scorers.

Runs all 4 ElevenLabs TTS eval scorers in sequence and reports combined
pass/fail. This is the recommended way to smoke-test the entire ElevenLabs
integration after SDK upgrades or API changes.

Cost: ~5 API calls per run (~$0.05-0.10)

Usage:
    python -m src.evals.run_tts_evals
"""
import os
import sys

from src.evals.score_ambient_audio import ScoreAmbientAudio
from src.evals.score_sound_effects import ScoreSoundEffects
from src.evals.score_tts_synthesis import ScoreTTSSynthesis
from src.evals.score_voice_design import ScoreVoiceDesign


def main() -> None:
    """Run all TTS eval scorers and report combined results."""
    # Check API key upfront
    api_key = os.environ.get("ELEVEN_API_KEY")
    if not api_key:
        print("ERROR: ELEVEN_API_KEY environment variable not set.")
        print("This runner requires a valid ElevenLabs API key.")
        sys.exit(1)

    print("=" * 60)
    print("TTS EVAL SUITE")
    print("=" * 60)
    print("\nRunning 4 ElevenLabs API integration scorers...\n")

    scorers = [
        ("TTS Synthesis", ScoreTTSSynthesis()),
        ("Voice Design", ScoreVoiceDesign()),
        ("Ambient Audio", ScoreAmbientAudio()),
        ("Sound Effects", ScoreSoundEffects()),
    ]

    results: list[tuple[str, bool]] = []

    for name, scorer in scorers:
        print(f"\n{'─' * 60}")
        print(f"Running: {name}")
        print(f"{'─' * 60}")

        try:
            # Setup
            scorer.setup()

            # Score (catches failures internally and exits on fail)
            # We need to catch SystemExit to continue with other scorers
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

            # Cleanup
            scorer.cleanup()

        except Exception as e:
            print(f"\nERROR in {name}: {e}")
            results.append((name, False))

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
