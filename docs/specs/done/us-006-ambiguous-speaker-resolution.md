# US-006: Ambiguous Speaker Resolution

## Problem Statement

Many dialogue beats come back with `character_id: null` because the AI
cannot identify the speaker from the section text alone. In chapter 1 of
*Pride and Prejudice*, all of Mr. Bennet's lines are unattributed — he never
appears in the `CharacterRegistry` despite speaking throughout the chapter.

This happens because each section is parsed in isolation. A bare quote like:

```
"You want to tell me, and I have no objection to hearing it."
```

contains no attribution text, so the AI correctly reports it cannot determine
the speaker. But a human reader — or an AI with the surrounding context —
would know from the preceding sections that this is Mr. Bennet replying to
Mrs. Bennet.

## Root Cause

The `AISectionParser` passes only the current section's text to the AI. It has
no visibility into adjacent sections. The registry provides character names but
not conversational context, so the AI cannot infer turn-taking or resolve
pronouns like "replied he" when "he" refers to a character mentioned paragraphs
earlier.

## Desired State

The AI section parser receives a **sliding window of surrounding sections** as
context alongside the current section. The window size is configurable
(default: 3 sections before, 1 after).

With this context the AI can:

- Follow conversational turn-taking across section boundaries
- Resolve pronouns ("he", "she", "his wife") to registry entries
- Infer the speaker of a bare quote from the flow of the dialogue exchange

The `character_id: null` rate on dialogue beats should drop to near zero
for well-structured dialogue.

## Data Model Changes

None. `Beat.character_id` and `CharacterRegistry` are unchanged. The
improvement is purely in what context is sent to the AI.

## AI Contract Change

`AISectionParser.parse()` receives an optional `context_window: list[Section]`
alongside the current section. The prompt is extended with a "surrounding
context" block that shows the text of the neighbouring sections (without
asking the AI to re-beat them — only to use them for speaker inference).

The parser ABC is updated to match:

```python
def parse(
    self,
    section: Section,
    registry: CharacterRegistry,
    context_window: list[Section] | None = None,
) -> tuple[list[Beat], CharacterRegistry]:
    ...
```

The caller (workflow) is responsible for slicing the correct window from
`chapter.sections` and passing it in.

## Acceptance Criteria

1. `AISectionParser.parse()` accepts an optional `context_window` parameter
2. When provided, the context window appears in the AI prompt as read-only
   surrounding context
3. `AIProjectGutenbergWorkflow` passes the 3 preceding sections (or fewer if
   at the start of a chapter) as the context window
4. Re-running chapter 1 of *Pride and Prejudice*: Mr. Bennet's `character_id`
   resolves correctly and he appears in the `CharacterRegistry`
5. All existing tests pass; new unit tests cover the prompt-building logic with
   and without a context window

## Out of Scope

- Cross-chapter context windows — deferred
- Retroactively re-resolving already-parsed sections — deferred
- Merging duplicate registry entries — deferred
