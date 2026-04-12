"""Golden-labeled passages for evaluating the AI Read layer.

Each passage is a real excerpt from Pride and Prejudice (Project Gutenberg)
with human-annotated ground truth for:
  - Expected characters (who speaks in this passage)
  - Expected segment types (dialogue vs narration counts)
  - Expected speaker attributions (which character_id for each dialogue line)

These are NOT exhaustive — they test the AI's core competencies:
  1. Character detection (recall: did it find the characters?)
  2. Segment classification (dialogue vs narration split)
  3. Speaker attribution (did it assign the right speaker?)

Passages are ordered by difficulty: simple → moderate → hard.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenPassage:
    """A passage with human-annotated ground truth."""

    name: str
    text: str
    # Expected characters that MUST appear in the registry after parsing
    # (character_id values, lowercase slugs)
    expected_characters: list[str] = field(default_factory=list)
    # Minimum number of dialogue segments expected
    min_dialogue_segments: int = 0
    # Minimum number of narration segments expected
    min_narration_segments: int = 0
    # Expected speaker attributions: list of (substring_of_text, character_id)
    # The scorer checks that a dialogue segment containing the substring
    # is attributed to the given character_id.
    expected_attributions: list[tuple[str, str]] = field(default_factory=list)
    # Book context
    book_title: str = "Pride and Prejudice"
    book_author: str = "Jane Austen"


# ── Passage 1: Simple — single speaker, clear narration ──────────────

PASSAGE_SIMPLE_NARRATION = GoldenPassage(
    name="simple_narration",
    text=(
        "It is a truth universally acknowledged, that a single man in "
        "possession of a good fortune, must be in want of a wife."
    ),
    expected_characters=[],  # narrator only, no named speakers
    min_dialogue_segments=0,
    min_narration_segments=1,
    expected_attributions=[],
)


# ── Passage 2: Simple — clear two-person dialogue ────────────────────

PASSAGE_SIMPLE_DIALOGUE = GoldenPassage(
    name="simple_dialogue",
    text=(
        '"My dear Mr. Bennet," said his lady to him one day, '
        '"have you heard that Netherfield Park is let at last?"\n\n'
        "Mr. Bennet replied that he had not.\n\n"
        '"But it is," returned she; "for Mrs. Long has just been here, '
        'and she told me all about it."'
    ),
    expected_characters=["mr_bennet", "mrs_bennet"],
    min_dialogue_segments=2,
    min_narration_segments=1,
    expected_attributions=[
        ("My dear Mr. Bennet", "mrs_bennet"),
        ("have you heard that Netherfield Park", "mrs_bennet"),
        ("But it is", "mrs_bennet"),
    ],
)


# ── Passage 3: Moderate — multi-turn dialogue, speaker inference ─────

PASSAGE_MULTI_TURN = GoldenPassage(
    name="multi_turn_dialogue",
    text=(
        '"Is he married or single?"\n\n'
        '"Oh! Single, my dear, to be sure! A single man of large '
        "fortune; four or five thousand a year. What a fine thing for "
        'our girls!"\n\n'
        '"How so? How can it affect them?"\n\n'
        '"My dear Mr. Bennet," replied his wife, "how can you be so '
        "tiresome! You must know that I am thinking of his marrying "
        'one of them."'
    ),
    expected_characters=["mr_bennet", "mrs_bennet"],
    min_dialogue_segments=4,
    min_narration_segments=0,
    expected_attributions=[
        ("Is he married or single", "mr_bennet"),
        ("Single, my dear, to be sure", "mrs_bennet"),
        ("How so", "mr_bennet"),
        ("how can you be so tiresome", "mrs_bennet"),
    ],
)


# ── Passage 4: Moderate — narration-heavy with embedded dialogue ─────

PASSAGE_EMBEDDED_DIALOGUE = GoldenPassage(
    name="embedded_dialogue",
    text=(
        "Mr. Bennet was so odd a mixture of quick parts, sarcastic humour, "
        "reserve, and caprice, that the experience of three-and-twenty years "
        "had been insufficient to make his wife understand his character. "
        "Her mind was less difficult to develop. She was a woman of mean "
        "understanding, little information, and uncertain temper. When she "
        "was discontented, she fancied herself nervous. The business of her "
        "life was to get her daughters married; its solace was visiting and news."
    ),
    expected_characters=[],  # Pure narration about the Bennets
    min_dialogue_segments=0,
    min_narration_segments=1,
    expected_attributions=[],
)


# ── Passage 5: Hard — three speakers, requires context inference ─────

PASSAGE_THREE_SPEAKERS = GoldenPassage(
    name="three_speakers",
    text=(
        '"If I can but see one of my daughters happily settled at '
        'Netherfield," said Mrs. Bennet to her husband, "and all '
        'the others equally well married, I shall have nothing to '
        'wish for."\n\n'
        '"If they are amiable, you will wish them to be settled near," '
        'said Elizabeth.\n\n'
        '"Certainly—but having Mr. Bingley for a neighbour—"\n\n'
        '"It would not signify if twenty such should come, since you '
        'will not visit them," replied her husband.'
    ),
    expected_characters=["mrs_bennet", "elizabeth", "mr_bennet"],
    min_dialogue_segments=4,
    min_narration_segments=0,
    expected_attributions=[
        ("one of my daughters happily settled", "mrs_bennet"),
        ("If they are amiable", "elizabeth"),
        ("having Mr. Bingley for a neighbour", "mrs_bennet"),
        ("twenty such should come", "mr_bennet"),
    ],
)


# ── Passage 6: Hard — long ping-pong, 17 turns, almost no tags ───────
#
# This is the passage that broke Sonnet.  Sections 18–34 of Chapter I:
# 17 rapid-fire alternating lines between Mr. and Mrs. Bennet with only
# two explicit attribution tags ("replied his wife" at turn 2, "replied
# he" at turn 11).  The AI must infer all other speakers purely from
# turn-taking pattern and conversational content.

PASSAGE_PING_PONG = GoldenPassage(
    name="ping_pong_ch1",
    text=(
        '"Is that his design in settling here?"\n\n'
        '"Design? Nonsense, how can you talk so! But it is very likely '
        "that he MAY fall in love with one of them, and therefore you "
        'must visit him as soon as he comes."\n\n'
        '"I see no occasion for that. You and the girls may go\u2014or '
        "you may send them by themselves, which perhaps will be still "
        "better; for as you are as handsome as any of them, Mr. Bingley "
        'might like you the best of the party."\n\n'
        '"My dear, you flatter me. I certainly HAVE had my share of '
        "beauty, but I do not pretend to be anything extraordinary now. "
        "When a woman has five grown-up daughters, she ought to give "
        'over thinking of her own beauty."\n\n'
        '"In such cases, a woman has not often much beauty to think of."\n\n'
        '"But, my dear, you must indeed go and see Mr. Bingley when he '
        'comes into the neighbourhood."\n\n'
        '"It is more than I engage for, I assure you."\n\n'
        '"But consider your daughters. Only think what an establishment '
        "it would be for one of them. Sir William and Lady Lucas are "
        "determined to go, merely on that account; for in general, you "
        "know, they visit no new comers. Indeed you must go, for it "
        'will be impossible for US to visit him, if you do not."\n\n'
        '"You are over scrupulous, surely. I dare say Mr. Bingley will '
        "be very glad to see you; and I will send a few lines by you "
        "to assure him of my hearty consent to his marrying whichever "
        "he chooses of the girls\u2014though I must throw in a good word "
        'for my little Lizzy."\n\n'
        '"I desire you will do no such thing. Lizzy is not a bit better '
        "than the others: and I am sure she is not half so handsome as "
        "Jane, nor half so good-humoured as Lydia. But you are always "
        'giving HER the preference."\n\n'
        '"They have none of them much to recommend them," replied he: '
        '"they are all silly and ignorant like other girls; but Lizzy '
        'has something more of quickness than her sisters."\n\n'
        '"Mr. Bennet, how can you abuse your own children in such a '
        "way? You take delight in vexing me. You have no compassion on "
        'my poor nerves."\n\n'
        '"You mistake me, my dear. I have a high respect for your '
        "nerves. They are my old friends. I have heard you mention them "
        'with consideration these twenty years at least."\n\n'
        '"Ah, you do not know what I suffer."\n\n'
        '"But I hope you will get over it, and live to see many young '
        'men of four thousand a year come into the neighbourhood."\n\n'
        '"It will be no use to us, if twenty such should come, since '
        'you will not visit them."\n\n'
        '"Depend upon it, my dear, that when there are twenty, I will '
        'visit them all."'
    ),
    expected_characters=["mr_bennet", "mrs_bennet"],
    min_dialogue_segments=17,
    min_narration_segments=0,
    expected_attributions=[
        # Turn 1: Mr. Bennet (dry, probing)
        ("Is that his design in settling here", "mr_bennet"),
        # Turn 2: Mrs. Bennet (exclaims, urges visit)
        ("Nonsense, how can you talk so", "mrs_bennet"),
        # Turn 3: Mr. Bennet (sarcastic — you're handsome enough)
        ("I see no occasion for that", "mr_bennet"),
        # Turn 4: Mrs. Bennet (flattered, deflects)
        ("you flatter me", "mrs_bennet"),
        # Turn 5: Mr. Bennet (cutting remark about beauty)
        ("a woman has not often much beauty", "mr_bennet"),
        # Turn 6: Mrs. Bennet (pleads again)
        ("you must indeed go and see Mr. Bingley", "mrs_bennet"),
        # Turn 7: Mr. Bennet (refuses)
        ("more than I engage for", "mr_bennet"),
        # Turn 8: Mrs. Bennet (invokes the daughters)
        ("consider your daughters", "mrs_bennet"),
        # Turn 9: Mr. Bennet (mock-agrees, teases about Lizzy)
        ("I will send a few lines by you", "mr_bennet"),
        # Turn 10: Mrs. Bennet (defends other daughters)
        ("I desire you will do no such thing", "mrs_bennet"),
        # Turn 11: Mr. Bennet ("replied he" — tagged)
        ("they are all silly and ignorant", "mr_bennet"),
        # Turn 12: Mrs. Bennet (offended)
        ("how can you abuse your own children", "mrs_bennet"),
        # Turn 13: Mr. Bennet (mock-respect for nerves)
        ("I have a high respect for your nerves", "mr_bennet"),
        # Turn 14: Mrs. Bennet (self-pity)
        ("you do not know what I suffer", "mrs_bennet"),
        # Turn 15: Mr. Bennet (wry hope)
        ("I hope you will get over it", "mr_bennet"),
        # Turn 16: Mrs. Bennet (exasperated)
        ("no use to us, if twenty such", "mrs_bennet"),
        # Turn 17: Mr. Bennet (final retort)
        ("when there are twenty, I will visit them all", "mr_bennet"),
    ],
)


# ── Aggregate ─────────────────────────────────────────────────────────

ALL_PASSAGES = [
    PASSAGE_SIMPLE_NARRATION,
    PASSAGE_SIMPLE_DIALOGUE,
    PASSAGE_MULTI_TURN,
    PASSAGE_EMBEDDED_DIALOGUE,
    PASSAGE_THREE_SPEAKERS,
    PASSAGE_PING_PONG,
]
