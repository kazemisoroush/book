# Trimmers

Deterministic post-LLM cleanup for the chapter_parser prompt output.

## BeatTrimmer

Abstract base with one method `trim(beats) -> beats`. Each concrete trimmer does one thing: transforms text, drops beats, or both. Trimmers are immutable and stateless; they return new beats rather than mutating in place.

## SentenceEndingTrimmer

Replaces a trailing `,` or `;` on each beat text with `.`. Leaves `.`, `?`, and `!` untouched. Handles trailing whitespace before the punctuation.

## CapitalizationTrimmer

Uppercases the first alphabetic character of each beat text. Skips leading whitespace and punctuation. No-op when the first letter is already uppercase or the text has no letters.

## QuotedPunctuationTrimmer

Moves a `,` or `;` that sits inside a closing quote (`"`, `”`, or `’`) to outside the quote. Normalises American-style `"Hello,"` to British-style `"Hello",` so it matches the convention used by Project Gutenberg sources.

## AudibilityTrimmer

Drops beats whose text contains no letters or digits (for example, the `* * * *` scene-break markers some sources use). Pure-punctuation and whitespace-only beats are also dropped.

## ParentheticalTrimmer

Removes wrapping `(` and `)` when a beat is a single parenthetical aside, like the narrator's `(For, you see, Alice had learnt several things of this sort.)`. Inner parentheses inside a larger sentence are left alone, since only whole-beat asides cause audible artefacts.

## EmDashTrimmer

Strips a leading em-dash (`—`) from each beat and replaces any remaining em-dash with `, `. Leading em-dashes appear on dialogue beats like `—Yes, that's about the right distance` where the dash only marked the start of speech in print, and inner em-dashes act as comma-strength pauses in TTS.

## apply_beat_trimmers

Runs a list of trimmers in order against every chapter in a `PromptOutput`. Renumbers beat ids contiguously per chapter after drops so the prompt's "ids sequential within each chapter" contract is preserved.

## Adding a trimmer

Create a new class implementing `BeatTrimmer`, write its test file alongside, and add it to the trimmer list passed into `AIWorkflow`.
