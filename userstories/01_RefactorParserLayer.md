# Refactor Book Parser Layer User Story

Book parser layer is an essential application layer in this project that converts raw text book into the `Book` data model. A book data model is demonstrated in the following JSON data structure:

```json
// Book data model
{
    "title": "Harry Potter and the Philosopher's Stone",
    "author": "J. K. Rowling",
    "characters": [
        {
            "name": "Narrator",
            "context": "Narrates the story throughout the book.",
            "narratedBy": "J. K. Rowling",
        },
        {
            "name": "Harry Potter",
            "aka": ["Harry", "Potter", "The Boy Who Lived"],
            "context": "Main character of Harry Potter books.",
            "narratedBy": "Daniel Radcliffe",
        },
        {
            "name": "Hermione Granger",
            "aka": ["Hermione", "Granger"],
            "context": "Muggle born witch who is one of Harry Potter's best friends. Rank #1 student in Hogwarts.",
            "narratedBy": "Emma Watson",
        },
        {
            "name": "Tom Riddle",
            "aka": ["Tom", "Riddle"],
            "context": "Lord Voldemort at teenage years",
            "narratedBy": "Christian Coulson",
        },
        {
            "name": "Lord Voldemort",
            "aka": ["The Dark Lord"],
            "context": "Lord Voldemort that dwells in professor Quirrell body",
            "narratedBy": "Richard Bremmer",
        },
        ...
    ],
    "chapters": [
        {
            "title": "Chapter 1",
            "sections": [
                {
                    "text": "Harry Potter has never even heard of Hogwarts when the letters start dropping on the doormat at number four, Privet Drive. Addressed in green ink on yellowish parchment with a purple seal, they are swiftly confiscated by his grisly aunt and uncle."
                },
                {
                    "text": "Then, on Harry's eleventh birthday, a great beetle-eyed giant of a man called Rubeus Hagrid bursts in with some astonishing news- Harry Potter is a wizard, and he has a place at Hogwarts School of Witchcraft and Wizardry. An incredible adventure is about to begin!"
                },
                ...
                {
                    "text": "\"I'm a what?\" gasped Harry. \"A wizard, o' course,\" said Hagrid, sitting back down on the sofa, which groaned and sank even lower, \"an' a thumpin' good'un I'd say, once yeh've been trained up a bit. With a mum an' dad like yours, what else would yeh be?\"",
                    "segments": [
                        {
                            "type": "dialogue",
                            "text": "I'm a what?",
                            "speaker": "Harry Potter"
                        },
                        {
                            "type": "narration",
                            "text": "gasped Harry."
                        },
                        {
                            "type": "dialogue",
                            "text": "A wizard, o' course,",
                            "speaker": "Rubeus Hagrid"
                        },
                        {
                            "type": "narration",
                            "text": "said Hagrid, sitting back down on the sofa, which groaned and sank even lower,"
                        },
                        {
                            "type": "dialogue",
                            "text": "an' a thumpin' good'un I'd say, once yeh've been trained up a bit. With a mum an' dad like yours, what else would yeh be?",
                            "speaker": "Rubeus Hagrid"
                        }
                    ]
                },
                ...
            ],
            ...
        },
        ...
    ],
}
```

Then the parser layer fine tunes this model using AI LLMs to break sections down into more fine tuned sections and add more context to the sections for better audio experience. Objective here is to refactor Book Parser layer for better maintenance, extendable, and automated testability, generalisable (being able to use the same code for ALL possible books).

## Book Information Recognition
Objective here is to know essential book information from its raw text content. Information like:
- Title
- Author
- Chapters
- Sections: Smaller parts of a chapter. E.g. paragraphs.

### Current Situation
The code is using heuristicts to determine the book basic information. This approach serves well for now we will revisit this later in the future if needed.

---

## Segment Recognition
Objective here is to break down sections (e.g. paragraphs) into smaller segments that alternate between narration and dialogue. This allows the audio generator to assign different voices to narrators and characters speaking.

For example, this text:
```
"I'm a what?" gasped Harry. "A wizard, o' course," said Hagrid, sitting back down on the sofa.
```

Should be broken into segments like:
1. Dialogue segment: "I'm a what?" (speaker: Harry Potter)
2. Narration segment: "gasped Harry."
3. Dialogue segment: "A wizard, o' course," (speaker: Rubeus Hagrid)
4. Narration segment: "said Hagrid, sitting back down on the sofa."

### Current Situation
Current parser uses pattern matching with regex (like `ATTRIBUTION_PATTERNS`) to detect dialogue quotes and split them from narration. This approach has limitations:
- Struggles with nested quotes or unusual punctuation
- Doesn't handle interrupted dialogue well
- Requires manual pattern maintenance for edge cases
- Not generalizable to different writing styles across books

### Desired State
Use AI LLMs to intelligently segment text into dialogue and narration:
- Send section text to the LLM with context about the book and characters
- LLM returns structured segments with:
  - Segment type (dialogue or narration)
  - Segment text
  - Speaker identification for dialogue
- AI can understand context and handle complex cases like:
  - Interrupted dialogue
  - Nested quotes
  - Implied speakers
  - Unusual formatting
- More robust and generalizable across different books and writing styles

### Example
```json
{
    "text": "\"I'm a what?\" gasped Harry. \"A wizard, o' course,\" said Hagrid, sitting back down on the sofa, which groaned and sank even lower, \"an' a thumpin' good'un I'd say, once yeh've been trained up a bit. With a mum an' dad like yours, what else would yeh be?\"",
    "segments": [
        {
            "type": "dialogue",
            "text": "I'm a what?",
            "speaker": "Harry Potter"
        },
        {
            "type": "narration",
            "text": "gasped Harry."
        },
        {
            "type": "dialogue",
            "text": "A wizard, o' course,",
            "speaker": "Rubeus Hagrid"
        },
        {
            "type": "narration",
            "text": "said Hagrid, sitting back down on the sofa, which groaned and sank even lower,"
        },
        {
            "type": "dialogue",
            "text": "an' a thumpin' good'un I'd say, once yeh've been trained up a bit. With a mum an' dad like yours, what else would yeh be?",
            "speaker": "Rubeus Hagrid"
        }
    ]
}
```
---

## Character Recognition and Registry
Objective here is to identify who is speaking at any time in the audiobook (narrator or specific characters). A character registry maintains a list of all characters with context that helps identify the speaker. Each character gets a unique voice.

### Current Situation
Current parser uses deterministic pattern matching (`ATTRIBUTION_PATTERNS`) to identify speakers. This is not generalizable and often fails with:
- Implicit speaker attribution ("He nodded" without saying who "he" is)
- Characters referred to by different names or pronouns
- Complex dialogue exchanges

### Desired State
Use AI LLMs to identify speakers and maintain the character registry:
- LLM analyzes dialogue segments with book context
- Identifies speaker by name, even with implicit references
- Builds and maintains character registry with:
  - Character name
  - Aliases (e.g., "Harry", "Potter", "The Boy Who Lived")
  - Context about the character
  - Voice narrator reference
- Application sends current character registry with each LLM request
- LLM returns updated registry with newly discovered characters or aliases
- More accurate speaker attribution across different books and writing styles

### Example
```json
[
    {
        "name": "Narrator",
        "context": "Narrates the story throughout the book.",
        "narratedBy": "J. K. Rowling",
    },
    {
        "name": "Harry Potter",
        "aka": ["Harry", "Potter", "The Boy Who Lived"],
        "context": "Main character of Harry Potter books.",
        "narratedBy": "Daniel Radcliffe",
    },
    {
        "name": "Hermione Granger",
        "aka": ["Hermione", "Granger"],
        "context": "Muggle born witch who is one of Harry Potter's best friends. Rank #1 student in Hogwarts.",
        "narratedBy": "Emma Watson",
    },
    {
        "name": "Tom Riddle",
        "aka": ["Tom", "Riddle"],
        "context": "Lord Voldemort at teenage years",
        "narratedBy": "Christian Coulson",
    },
    {
        "name": "Lord Voldemort",
        "aka": ["The Dark Lord"],
        "context": "Lord Voldemort that dwells in professor Quirrell body",
        "narratedBy": "Richard Bremmer",
    },
    ...
]
```

## Rules
1. TDD
2. SOLID
3. Do not be affraid to remove files entirely and start over.
4. Do not change user story file during your changes.
5. All tests pass locally
6. All linter rules pass locally