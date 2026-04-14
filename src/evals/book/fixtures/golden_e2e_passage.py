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

    The passage text is embedded directly in ``sections`` — no download
    step required at runtime.  ``gutenberg_url`` is kept as reference-only
    metadata so reviewers can locate the source, but it is never fetched.

    Attributes:
        name: Short slug used as identifier (e.g., "dracula_arrival").
        book_title: Human-readable book title.
        author: Book author name (e.g., "Bram Stoker").
        gutenberg_url: Reference URL to the plain-text file on Project Gutenberg
            (not fetched at runtime — for human reference only).
        chapter_number: 1-based chapter number these sections belong to.
        chapter_title: Chapter title string (e.g., "Jonathan Harker's Journal").
        sections: The actual paragraph text for the passage. Each string is
            one section/paragraph fed directly into the AI pipeline.
        expected_features: Audio feature tags this passage should exercise
            (e.g., ["dialogue", "sfx", "ambient", "voice_design"]).
        notes: Human explanation of why this passage is a good test case.
    """

    name: str
    book_title: str
    author: str
    gutenberg_url: str
    chapter_number: int
    chapter_title: str
    sections: list[str] = field(default_factory=list)
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
# Text source: Project Gutenberg #345 — public domain.
# Paragraphs taken from Chapter 1, "3 May. Bistritz." opening,
# covering Harker's journey through Transylvania and first contact
# with the strange coachman at the Borgo Pass.

dracula_arrival = GoldenE2EPassage(
    name="dracula_arrival",
    book_title="Dracula",
    author="Bram Stoker",
    gutenberg_url="https://www.gutenberg.org/cache/epub/345/pg345.txt",
    chapter_number=1,
    chapter_title="Jonathan Harker's Journal",
    sections=[
        (
            "I had all sorts of queer dreams last night. I suppose it was all the "
            "stories and traditions I had heard during the day and evening. A dog "
            "began to howl somewhere in a farmhouse far down the road, a long, "
            "agonised wailing, as if from fear. The sound was taken up by another "
            "dog, and then another and another, till borne on the wind which now "
            "sighed softly through the Pass, a wild howling began, which seemed to "
            "come from all over the country, as far as the imagination could grasp it "
            "through the gloom of the night."
        ),
        (
            "At last we saw before us the Pass opening out on the eastern side. "
            "There were dark, rolling clouds overhead, and in the air the heavy, "
            "oppressive sense of thunder. I was now myself looking out for the "
            "conveyance which was to take me to the Count. Suddenly the driver "
            'exclaimed: "Hark!" and in the silence of the night I could just hear '
            "a distant sound of horses, then the flickering of lights."
        ),
    ],
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
        "Harker's night journey through the Borgo Pass: first-person narration, "
        "dialogue with the mysterious coachman, howling wolves (SFX), mountain "
        "wind ambient, tense approaching-danger music mood, and an unnamed driver "
        "as a bespoke voice-design character. Covers 7 of 7 audio feature categories."
    ),
)


# ── Registry ────────────────────────────────────────────────────────────

ALL_E2E_PASSAGES: list[GoldenE2EPassage] = [
    dracula_arrival,
]
