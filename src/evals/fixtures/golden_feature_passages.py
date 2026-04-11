"""Golden-labeled passages for evaluating AI feature completeness.

Each passage is a real excerpt from a public-domain Project Gutenberg text,
with human-annotated ground truth for which features the AI should emit:
  - Expected segment types (dialogue, narration, sound_effect, vocal_effect)
  - Minimum segment counts per type
  - Expected emotions on dialogue segments
  - Whether scene detection should fire
  - Precision constraints (e.g. no hallucinated sound effects)

These test the AI's ability to emit ALL supported features, not just one.
The existing score_ai_read and score_sound_effect_detection evals check
features in isolation; this eval checks they all work together.

Passages are ordered: feature-rich → emotion-focused → quiet (precision).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenFeaturePassage:
    """A passage with human-annotated feature ground truth."""

    name: str
    text: str
    book_title: str
    book_author: str
    # Expected segment types the AI MUST emit (recall)
    expected_segment_types: list[str] = field(default_factory=list)
    # Minimum counts per type (e.g. {"dialogue": 2, "sound_effect": 1})
    min_segment_counts: dict[str, int] = field(default_factory=dict)
    # Expected emotion tags — at least one segment should fuzzy-match each
    expected_emotions: list[str] = field(default_factory=list)
    # Whether scene detection should fire (at least one segment gets scene_id)
    expect_scene: bool = False
    # Expected vocal effect labels (fuzzy-matched against vocal_effect text)
    expected_vocal_effect_labels: list[str] = field(default_factory=list)
    # If True, zero SOUND_EFFECT segments is the correct answer (precision)
    expect_no_sound_effects: bool = False
    # If True, zero VOCAL_EFFECT segments is the correct answer (precision)
    expect_no_vocal_effects: bool = False


# ── Passage 1: Feature-rich — dialogue, sounds, emotion, scene ─────────
# From "The Hound of the Baskervilles" by Arthur Conan Doyle (Chapter 14)
# Contains: narration, dialogue (2 speakers), sound effects (scream, pistol
# click), vocal effects (gasp, whisper), strong emotions (fear, shock),
# clear scene (outdoor moor at night).

PASSAGE_FEATURE_RICH = GoldenFeaturePassage(
    name="feature_rich",
    text=(
        "A terrible scream\u2014a prolonged yell of horror and anguish\u2014burst "
        "out of the silence of the moor. That frightful cry turned the blood "
        "to ice in my veins.\n\n"
        '"Oh, my God!" I gasped. "What is it? What does it mean?"\n\n'
        "Holmes had sprung to his feet, and I could see his dark, athletic "
        "outline at the door of the hut, his shoulders stooping, his head "
        "thrust forward, his face peering into the darkness.\n\n"
        '"Hush!" whispered Holmes, and I heard the sharp click of a cocking '
        "pistol. "
        '"Where is it?" Holmes whispered; and I knew from the thrill of his '
        "voice that he, the man of iron, was shaken to the soul."
    ),
    book_title="The Hound of the Baskervilles",
    book_author="Arthur Conan Doyle",
    expected_segment_types=["narration", "dialogue", "sound_effect"],
    min_segment_counts={"narration": 1, "dialogue": 2, "sound_effect": 1},
    expected_emotions=["fear", "shock", "whisper"],
    expect_scene=True,
    expected_vocal_effect_labels=["gasp"],
)


# ── Passage 2: Emotion shifts — multiple emotions in dialogue ──────────
# From "Frankenstein" by Mary Shelley (Chapter 10 — the creature speaks)
# Contains: narration, dialogue (2 speakers), strong emotion shifts
# (rage → pity → anguish), scene (mountain glacier).
# No explicit sound effects — precision test for SFX.

PASSAGE_EMOTION_SHIFTS = GoldenFeaturePassage(
    name="emotion_shifts",
    text=(
        '"Devil," I exclaimed, "do you dare approach me? And do not you '
        "fear the fierce vengeance of my arm wreaked on your miserable head? "
        'Begone, vile insect! Or rather, stay, that I may trample you to dust!"\n\n'
        '"I expected this reception," said the d\u00e6mon. "All men hate the '
        "wretched; how, then, must I be hated, who am miserable beyond all "
        "living things! Yet you, my creator, detest and spurn me, thy creature, "
        'to whom thou art bound by ties only dissoluble by the annihilation '
        'of one of us."\n\n'
        "I trembled with rage and horror."
    ),
    book_title="Frankenstein",
    book_author="Mary Shelley",
    expected_segment_types=["narration", "dialogue"],
    min_segment_counts={"narration": 1, "dialogue": 2},
    expected_emotions=["rage", "anger", "bitter", "misera"],
    expect_scene=True,
    expect_no_sound_effects=True,
)


# ── Passage 3: Vocal effects — sighs, breaths, laughter ───────────────
# From "Dracula" by Bram Stoker (Chapter 2 — Harker's first night)
# Contains: narration, vocal effects (sigh/breath implied by the eerie
# setting), scene (castle interior at night).

PASSAGE_VOCAL_EFFECTS = GoldenFeaturePassage(
    name="vocal_effects",
    text=(
        "Then a dog began to howl somewhere in a farmhouse far down the road\u2014"
        "a long, agonised wailing, as if from fear. The sound was taken up by "
        "another dog, and then another and another, till, borne on the wind "
        "which now sighed softly through the Pass, a wild howling began, which "
        "seemed to come from all over the country.\n\n"
        '"I say, driver, what is that?" I called out.\n\n'
        "He merely cracked his whip and drove on. Then the horses began to "
        "tremble and snort with terror."
    ),
    book_title="Dracula",
    book_author="Bram Stoker",
    expected_segment_types=["narration", "dialogue", "sound_effect"],
    min_segment_counts={"narration": 1, "dialogue": 1, "sound_effect": 1},
    expected_emotions=["fear"],
    expect_scene=True,
    expected_vocal_effect_labels=[],
)


# ── Passage 4: Quiet narration — precision test ───────────────────────
# From "Pride and Prejudice" by Jane Austen (Chapter 1 ending)
# Contains: pure narration, no dialogue, no sounds, no vocal effects.
# The AI must NOT hallucinate any of these.

PASSAGE_QUIET_NARRATION = GoldenFeaturePassage(
    name="quiet_narration",
    text=(
        "Mr. Bennet was so odd a mixture of quick parts, sarcastic humour, "
        "reserve, and caprice, that the experience of three-and-twenty years "
        "had been insufficient to make his wife understand his character. "
        "Her mind was less difficult to develop. She was a woman of mean "
        "understanding, little information, and uncertain temper. When she "
        "was discontented, she fancied herself nervous. The business of her "
        "life was to get her daughters married; its solace was visiting and news."
    ),
    book_title="Pride and Prejudice",
    book_author="Jane Austen",
    expected_segment_types=["narration"],
    min_segment_counts={"narration": 1},
    expected_emotions=[],
    expect_scene=False,
    expect_no_sound_effects=True,
    expect_no_vocal_effects=True,
)


# ── Aggregate ─────────────────────────────────────────────────────────

ALL_FEATURE_PASSAGES = [
    PASSAGE_FEATURE_RICH,
    PASSAGE_EMOTION_SHIFTS,
    PASSAGE_VOCAL_EFFECTS,
    PASSAGE_QUIET_NARRATION,
]
