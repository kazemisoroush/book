"""AI provider interface for character detection and dialogue classification.

This module defines the abstract interface that all AI providers must implement.
Supports multiple backends: AWS Bedrock, OpenAI, local models, etc.
"""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class DialogueClassification:
    """Result of dialogue classification."""
    is_dialogue: bool
    speaker: Optional[str] = None
    confidence: float = 1.0


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def classify_dialogue(self, paragraph: str, context: dict) -> DialogueClassification:
        """Classify whether quoted text is dialogue and identify the speaker.

        Args:
            paragraph: The paragraph containing quoted text
            context: Dictionary with context information:
                - recent_paragraphs: List of previous paragraphs
                - known_characters: List of known character names
                - active_speakers: List of currently active speakers in conversation

        Returns:
            DialogueClassification with is_dialogue flag and speaker name
        """
        pass

    @abstractmethod
    def resolve_speaker(self, descriptor: str, context: dict) -> str:
        """Resolve a speaker descriptor to a canonical character name.

        Args:
            descriptor: The speaker descriptor (e.g., "his wife", "she", "lady")
            context: Dictionary with context information:
                - paragraph: The current paragraph
                - recent_paragraphs: List of previous paragraphs
                - known_characters: List of known character names

        Returns:
            Canonical character name (e.g., "Mrs. Bennet")
        """
        pass

    @abstractmethod
    def extract_characters(self, book_content: str) -> dict[str, list[str]]:
        """Extract all characters and their variations from a book.

        Args:
            book_content: The full text of the book

        Returns:
            Dictionary mapping canonical names to list of variations
            Example: {"Mrs. Bennet": ["his wife", "his lady", "she", "lady"]}
        """
        pass
