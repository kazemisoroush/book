"""Character registry for tracking and identifying characters in a book.

This module maintains a registry of characters discovered while parsing a book.
It uses heuristics for fast path and AI for ambiguous cases.
"""
import json
import re
from typing import Optional
from dataclasses import dataclass, asdict
from src.ai import AIProvider


@dataclass
class Character:
    """A character in the book."""
    canonical_name: str
    aliases: list[str]
    context: str
    first_seen_chapter: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


class CharacterRegistry:
    """Registry of characters discovered in a book.

    The registry grows incrementally as the book is parsed:
    1. Heuristics extract speaker descriptors from text
    2. If descriptor is known → use canonical name (fast path, no AI)
    3. If descriptor is unknown → ask AI to identify and update registry

    The AI maintains and refines the registry itself, treating it as evolving context.
    """

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        """Initialize character registry.

        Args:
            ai_provider: Optional AI provider for ambiguous cases.
                         If None, only heuristics will be used.
        """
        self.ai_provider = ai_provider
        self.characters: dict[str, Character] = {}
        self.current_chapter = 0

    def set_chapter(self, chapter_num: int):
        """Set the current chapter being parsed."""
        self.current_chapter = chapter_num

    def get_canonical_name(self, descriptor: str) -> Optional[str]:
        """Get canonical name for a descriptor (fast lookup).

        Args:
            descriptor: Speaker descriptor (e.g., "Mrs. Bennet", "his wife", "she")

        Returns:
            Canonical character name if found, None otherwise
        """
        descriptor_lower = descriptor.lower()

        # Check if it's already a canonical name
        for name, character in self.characters.items():
            if name.lower() == descriptor_lower:
                return name

            # Check aliases
            if any(alias.lower() == descriptor_lower for alias in character.aliases):
                return name

        return None

    def identify_speaker(
        self,
        speaker_descriptor: str,
        paragraph: str,
        prev_paragraph: Optional[str] = None
    ) -> str:
        """Identify the canonical name for a speaker.

        Uses heuristics first (fast path), then AI if needed.

        Args:
            speaker_descriptor: The descriptor from attribution (e.g., "his wife", "she")
            paragraph: The current paragraph containing the dialogue
            prev_paragraph: The previous paragraph for context

        Returns:
            Canonical character name
        """
        # Fast path: Check if we already know this descriptor
        canonical = self.get_canonical_name(speaker_descriptor)
        if canonical:
            return canonical

        # Need AI to identify
        if not self.ai_provider:
            # No AI available, use descriptor as-is
            return self._normalize_name(speaker_descriptor)

        # Build prompt for AI
        prompt = self._build_identification_prompt(
            speaker_descriptor,
            paragraph,
            prev_paragraph
        )

        try:
            response = self.ai_provider.generate(prompt, max_tokens=2000)
            result = json.loads(response)

            # Update our registry with AI's version
            self._update_from_ai_response(result)

            return result.get('speaker', self._normalize_name(speaker_descriptor))

        except (json.JSONDecodeError, Exception) as e:
            # Fallback: use normalized descriptor
            print(f"Warning: AI identification failed: {e}")
            return self._normalize_name(speaker_descriptor)

    def _build_identification_prompt(
        self,
        descriptor: str,
        paragraph: str,
        prev_paragraph: Optional[str]
    ) -> str:
        """Build the prompt for AI character identification."""
        # Convert registry to JSON for AI
        registry_dict = {
            name: {
                'aliases': char.aliases,
                'context': char.context,
                'first_seen_chapter': char.first_seen_chapter
            }
            for name, char in self.characters.items()
        }

        context_parts = []
        if prev_paragraph:
            context_parts.append(f"Previous paragraph:\n{prev_paragraph}")
        context_parts.append(f"\nCurrent paragraph:\n{paragraph}")

        prompt = f"""You are analyzing a novel to identify characters and maintain a character registry.

Current character registry (JSON):
{json.dumps(registry_dict, indent=2) if registry_dict else "{{}}"}

{chr(10).join(context_parts)}

Task:
The text contains a speaker descriptor: "{descriptor}"

1. Identify who "{descriptor}" refers to based on the context and registry
2. If this is a NEW character:
   - Create an entry with a canonical name (e.g., "Mrs. Bennet", "Elizabeth Bennet")
   - Add 2-3 sentences of context for future identification (relationships, role, traits)
3. If this is an EXISTING character with a new alias:
   - Add "{descriptor}" to their aliases list
   - Optionally refine their context if new information is revealed
4. Return the COMPLETE updated registry

Respond with JSON only:
{{
  "speaker": "canonical name",
  "registry": {{
    "Canonical Name": {{
      "aliases": ["list", "of", "aliases"],
      "context": "2-3 sentences about the character",
      "first_seen_chapter": chapter_number
    }}
  }}
}}

Guidelines:
- Use full names for canonical names (e.g., "Mrs. Bennet" not "Bennet")
- Context should focus on: relationships, role, key traits (not plot details)
- Don't add generic pronouns like "he"/"she" as permanent aliases
- Keep existing registry entries and only add/update as needed"""

        return prompt

    def _update_from_ai_response(self, result: dict):
        """Update the registry from AI's response."""
        registry_data = result.get('registry', {})

        for name, data in registry_data.items():
            if name in self.characters:
                # Update existing character
                character = self.characters[name]
                # Merge aliases (avoid duplicates)
                new_aliases = set(character.aliases) | set(data.get('aliases', []))
                character.aliases = list(new_aliases)
                # Update context if provided
                if data.get('context'):
                    character.context = data['context']
            else:
                # New character
                self.characters[name] = Character(
                    canonical_name=name,
                    aliases=data.get('aliases', [name]),
                    context=data.get('context', ''),
                    first_seen_chapter=data.get('first_seen_chapter', self.current_chapter)
                )

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for consistency."""
        # Capitalize first letter of each word
        return ' '.join(word.capitalize() for word in name.split())

    def get_all_characters(self) -> dict[str, Character]:
        """Get all characters in the registry."""
        return self.characters.copy()

    def to_dict(self) -> dict:
        """Convert registry to dictionary for serialization."""
        return {
            name: char.to_dict()
            for name, char in self.characters.items()
        }

    def from_dict(self, data: dict):
        """Load registry from dictionary."""
        self.characters = {
            name: Character(**char_data)
            for name, char_data in data.items()
        }
