"""Golden-labeled passages for evaluating SOUND_EFFECT detection by the AI parser.

Each passage is a real excerpt from a public-domain Project Gutenberg text,
with human-annotated ground truth for:
  - Expected sound effects (short labels the AI should detect)
  - Whether the passage should produce zero sound effects (precision test)

These test the AI's ability to:
  1. Detect explicit diegetic sound events → SOUND_EFFECT segments (recall)
  2. Avoid hallucinating sounds from implied actions (precision)
  3. Set character_id=None on SOUND_EFFECT segments (precision)
  4. Provide meaningful text labels for detected sounds (recall)

Passages are ordered by difficulty: clear sounds → mixed → no sounds.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenSoundEffectPassage:
    """A passage with human-annotated sound-effect ground truth."""

    name: str
    text: str
    # Short labels for sounds that MUST appear as SOUND_EFFECT segments.
    # The scorer fuzzy-matches each label against SOUND_EFFECT segment text.
    expected_sound_effect_labels: list[str] = field(default_factory=list)
    # Minimum number of SOUND_EFFECT segments expected (loose floor)
    min_sound_effect_segments: int = 0
    # If True, zero SOUND_EFFECT segments is the correct answer (precision test)
    expect_no_sound_effects: bool = False
    # Book context for the prompt builder
    book_title: str = "Test Book"
    book_author: str = "Test Author"


# ── Passage 1: Clear explicit sounds ────────────────────────────────────
# From "The Hound of the Baskervilles" by Arthur Conan Doyle (Chapter 14)
# Contains: scream/cry, footsteps (explicit running sounds)

PASSAGE_EXPLICIT_SOUNDS = GoldenSoundEffectPassage(
    name="explicit_sounds",
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
    expected_sound_effect_labels=["scream", "click"],
    min_sound_effect_segments=2,
    book_title="The Hound of the Baskervilles",
    book_author="Arthur Conan Doyle",
)


# ── Passage 2: Sounds mixed with dialogue ──────────────────────────────
# From "Dracula" by Bram Stoker (Chapter 2 — approaching the castle)
# Contains: howling, cracking of whip

PASSAGE_MIXED_SOUNDS_DIALOGUE = GoldenSoundEffectPassage(
    name="mixed_sounds_dialogue",
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
    expected_sound_effect_labels=["howl", "crack"],
    min_sound_effect_segments=2,
    book_title="Dracula",
    book_author="Bram Stoker",
)


# ── Passage 3: Single prominent sound ──────────────────────────────────
# From "Frankenstein" by Mary Shelley (Chapter 5 — creation night)
# Contains: thunder (explicit)

PASSAGE_SINGLE_SOUND = GoldenSoundEffectPassage(
    name="single_sound",
    text=(
        "It was on a dreary night of November that I beheld the accomplishment "
        "of my toils. With an anxiety that almost amounted to agony, I "
        "collected the instruments of life around me, that I might infuse a "
        "spark of being into the lifeless thing that lay at my feet. It was "
        "already one in the morning; the rain pattered dismally against the "
        "panes, and my candle was nearly burnt out, when, by the glimmer of "
        "the half-extinguished light, I saw the dull yellow eye of the "
        "creature open; it breathed hard, and a convulsive motion agitated "
        "its limbs."
    ),
    expected_sound_effect_labels=["rain"],
    min_sound_effect_segments=1,
    book_title="Frankenstein",
    book_author="Mary Shelley",
)


# ── Passage 4: No explicit sounds (pure narration) ─────────────────────
# From "Pride and Prejudice" by Jane Austen (Chapter 1 ending)
# Contains: NO explicit sound events. Actions are described but not heard.

PASSAGE_NO_SOUNDS_NARRATION = GoldenSoundEffectPassage(
    name="no_sounds_narration",
    text=(
        "Mr. Bennet was so odd a mixture of quick parts, sarcastic humour, "
        "reserve, and caprice, that the experience of three-and-twenty years "
        "had been insufficient to make his wife understand his character. "
        "Her mind was less difficult to develop. She was a woman of mean "
        "understanding, little information, and uncertain temper. When she "
        "was discontented, she fancied herself nervous. The business of her "
        "life was to get her daughters married; its solace was visiting and news."
    ),
    expected_sound_effect_labels=[],
    min_sound_effect_segments=0,
    expect_no_sound_effects=True,
    book_title="Pride and Prejudice",
    book_author="Jane Austen",
)


# ── Passage 5: No explicit sounds (dialogue only) ──────────────────────
# From "Pride and Prejudice" by Jane Austen (Chapter 1)
# Contains: pure dialogue, no sound events. The AI must NOT invent sounds.

PASSAGE_NO_SOUNDS_DIALOGUE = GoldenSoundEffectPassage(
    name="no_sounds_dialogue",
    text=(
        '"My dear Mr. Bennet," said his lady to him one day, '
        '"have you heard that Netherfield Park is let at last?"\n\n'
        "Mr. Bennet replied that he had not.\n\n"
        '"But it is," returned she; "for Mrs. Long has just been here, '
        'and she told me all about it."'
    ),
    expected_sound_effect_labels=[],
    min_sound_effect_segments=0,
    expect_no_sound_effects=True,
    book_title="Pride and Prejudice",
    book_author="Jane Austen",
)


# ── Aggregate ─────────────────────────────────────────────────────────

ALL_SOUND_EFFECT_PASSAGES = [
    PASSAGE_EXPLICIT_SOUNDS,
    PASSAGE_MIXED_SOUNDS_DIALOGUE,
    PASSAGE_SINGLE_SOUND,
    PASSAGE_NO_SOUNDS_NARRATION,
    PASSAGE_NO_SOUNDS_DIALOGUE,
]
