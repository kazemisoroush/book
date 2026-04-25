"""Planted test violations — one per Test Auditor rule.

NOT a test file — intentionally named without _test.py suffix so that
pytest, agents, and glob patterns for *_test.py never discover it.
The eval scorer copies this into domain/ as a real _test.py file at setup time.

The Test Auditor should delete tests marked SHOULD_DELETE and keep tests
marked SHOULD_SURVIVE.  The eval scorer checks this.

Each test is tagged with the rule it violates (or "clean") in its docstring
so the scorer can report per-rule precision/recall.
"""
import inspect
from unittest.mock import patch, MagicMock

from src.domain.models import Beat, BeatType, Character


# ── Rule 1: At most 1 mock per test ─────────────────────────────────────

class TestRule1TwoMocks:
    """SHOULD_DELETE | rule:max-one-mock"""

    def test_process_with_two_mocks(self) -> None:
        """Uses two mocks — violates the 1-mock limit."""
        with patch("src.domain.models.Beat") as mock_seg, \
             patch("src.domain.models.Chapter") as mock_ch:
            mock_seg.return_value.text = "hello"
            mock_ch.return_value.title = "Ch1"
            assert mock_seg.return_value.text == "hello"


# ── Rule 2: Missing Arrange / Act / Assert ──────────────────────────────

class TestRule2NoAAA:
    """SHOULD_DELETE | rule:aaa-structure"""

    def test_jumbled_logic(self) -> None:
        """No clear AAA structure — everything mashed together."""
        seg = Beat(text="hi", beat_type=BeatType.NARRATION)
        assert seg.text == "hi"
        seg2 = Beat(text="bye", beat_type=BeatType.DIALOGUE)
        assert seg2.text == "bye"
        assert seg.beat_type != seg2.beat_type


# ── Rule 3: Constructor-assertion test ──────────────────────────────────

class TestRule3ConstructorAssertion:
    """SHOULD_DELETE | rule:no-constructor-assertion"""

    def test_character_fields_match_init_args(self) -> None:
        """Only checks that fields equal what was passed to __init__."""
        # Arrange
        ch = Character(character_id="c1", name="Alice", sex="female", age="young")

        # Assert
        assert ch.character_id == "c1"
        assert ch.name == "Alice"
        assert ch.sex == "female"
        assert ch.age == "young"


# ── Rule 4: Type-check test ─────────────────────────────────────────────

class TestRule4TypeCheck:
    """SHOULD_DELETE | rule:no-type-check"""

    def test_segment_is_a_segment(self) -> None:
        """Only assertion is isinstance — tests the language, not code."""
        # Arrange
        seg = Beat(text="x", beat_type=BeatType.NARRATION)

        # Assert
        assert isinstance(seg, Beat)


# ── Rule 5: Hard-coded value test ───────────────────────────────────────

class TestRule5HardCodedValue:
    """SHOULD_DELETE | rule:no-hardcoded-value"""

    def test_default_segment_type_value(self) -> None:
        """Asserts a constant equals a literal — tests typing, not behaviour."""
        # Assert
        assert BeatType.NARRATION.value == "narration"
        assert BeatType.DIALOGUE.value == "dialogue"


# ── Rule 6: Signature-reflection test ───────────────────────────────────

class TestRule6SignatureReflection:
    """SHOULD_DELETE | rule:no-signature-reflection"""

    def test_segment_init_has_text_param(self) -> None:
        """Uses inspect.signature to check parameter names."""
        sig = inspect.signature(Beat)
        assert "text" in sig.parameters
        assert "segment_type" in sig.parameters


# ── Rule 7: Near-duplicate tests (mergeable) ─────────────────────────────

class TestRule7MergeableDuplicates:
    """SHOULD_MERGE | rule:merge-near-duplicates"""

    def test_dialogue_segment_is_dialogue(self) -> None:
        """Checks is_dialogue — same arrange/act as next test."""
        # Arrange
        seg = Beat(text="Hello!", beat_type=BeatType.DIALOGUE)

        # Act
        result_dialogue = seg.is_dialogue()

        # Assert
        assert result_dialogue is True

    def test_dialogue_segment_is_not_narration(self) -> None:
        """Checks is_narration — same arrange as previous test."""
        # Arrange
        seg = Beat(text="Hello!", beat_type=BeatType.DIALOGUE)

        # Act
        result_narration = seg.is_narration()

        # Assert
        assert result_narration is False

    def test_dialogue_segment_is_not_illustration(self) -> None:
        """Checks is_illustration — same arrange as previous tests."""
        # Arrange
        seg = Beat(text="Hello!", beat_type=BeatType.DIALOGUE)

        # Act
        result_illustration = seg.is_illustration()

        # Assert
        assert result_illustration is False


# ── Rule 8: ABC-instantiation test ────────────────────────────────────────

class TestRule8ABCInstantiation:
    """SHOULD_DELETE | rule:no-abc-instantiation"""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Tests that an ABC raises TypeError — tests the language, not code."""
        import pytest
        from abc import ABC, abstractmethod

        class MyABC(ABC):
            @abstractmethod
            def do_thing(self) -> None: ...

        # Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            MyABC()  # type: ignore[abstract]


# ── Rule 9: Not-None constructor assertion ────────────────────────────────

class TestRule9NotNoneConstructor:
    """SHOULD_DELETE | rule:no-not-none-assertion"""

    def test_concrete_implementation_can_be_instantiated(self) -> None:
        """Only asserts `is not None` after construction — tests the language."""
        # Arrange / Act
        seg = Beat(text="x", beat_type=BeatType.NARRATION)

        # Assert
        assert seg is not None


# ── Clean tests that MUST survive ────────────────────────────────────────

class TestCleanBehavioural:
    """SHOULD_SURVIVE | rule:clean"""

    def test_narration_segment_is_narration(self) -> None:
        """Tests real behaviour — is_narration() method logic."""
        # Arrange
        seg = Beat(text="The sun rose.", beat_type=BeatType.NARRATION)

        # Act
        result = seg.is_narration()

        # Assert
        assert result is True

    def test_dialogue_segment_is_not_narration(self) -> None:
        """Tests real behaviour — type discriminator returns False."""
        # Arrange
        seg = Beat(text="Hello!", beat_type=BeatType.DIALOGUE)

        # Act
        result = seg.is_narration()

        # Assert
        assert result is False
