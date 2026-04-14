"""Golden passages for end-to-end listening evaluation.

Each GoldenE2EPassage represents a carefully selected excerpt from a
public-domain Project Gutenberg book that exercises all major audio
features of the pipeline:
  - Narration (baseline narrator voice)
  - Dialogue (2+ distinct character voices)
  - Emotion shifts (fear, unease, wonder)
  - Sound effects (howling wolves, carriage, door)
  - Scene/ambient change (outside → inside castle)
  - Background music (tense/mysterious)
  - Voice design (character-specific bespoke voice)

These are NOT pytest fixtures — they are reference data used by the
eval script src/evals/run_e2e_listening_eval.py for human listening
evaluation.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenE2EPassage:
    """A passage for end-to-end listening evaluation.

    Attributes:
        name: Short slug used as identifier (e.g., "dracula_arrival").
        book_title: Human-readable book title.
        gutenberg_url: Direct URL to the plain-text file on Project Gutenberg.
        start_chapter: 1-based chapter index to start parsing (inclusive).
        end_chapter: 1-based chapter index to end parsing (inclusive).
        expected_features: Audio feature tags this passage should exercise
            (e.g., ["dialogue", "sfx", "ambient", "voice_design"]).
        notes: Human explanation of why this passage is a good test case.
    """

    name: str
    book_title: str
    gutenberg_url: str
    start_chapter: int
    end_chapter: int
    expected_features: list[str] = field(default_factory=list)
    notes: str = ""


# ── Dracula, Chapter 1 — Jonathan Harker's arrival ─────────────────────
# From "Dracula" by Bram Stoker (Project Gutenberg #345)
#
# Why this passage?
# - Narration: Harker's first-person journal voice
# - Dialogue: Conversation with the mysterious coachman, then Count Dracula
# - Emotion: Unease, fear, supernatural dread
# - Sound effects: Howling wolves, carriage wheels, creaking castle door
# - Scene change: Exposed mountain pass → grand castle entrance hall
# - Ambient: Mountain wind, distant wolves → stone corridor reverb
# - Music: Tense/mysterious mood fits the gothic setting
# - Voice design: Count Dracula (older male, commanding, Transylvanian)
#
# Target section: Chapter 1, "3 May. Bistritz." — first ~250 words covering
# the arrival at the Borgo Pass and meeting with the coachman.

dracula_arrival = GoldenE2EPassage(
    name="dracula_arrival",
    book_title="Dracula",
    gutenberg_url="https://www.gutenberg.org/cache/epub/345/pg345.txt",
    start_chapter=1,
    end_chapter=1,
    expected_features=[
        "narration",
        "dialogue",
        "emotion",
        "sfx",
        "ambient",
        "scene_transition",
        "voice_design",
    ],
    notes=(
        "Harker's arrival at Borgo Pass: first-person narration, dialogue with "
        "the coachman, howling wolves (SFX), mountain wind ambient, scene change "
        "to castle interior, tense music mood, and Count Dracula as a bespoke "
        "voice-design character. Covers 7 of 7 audio feature categories."
    ),
)


# ── Registry ────────────────────────────────────────────────────────────

ALL_E2E_PASSAGES: list[GoldenE2EPassage] = [
    dracula_arrival,
]
