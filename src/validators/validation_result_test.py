"""Tests for the ValidationResult measurement DTO."""
from src.validators.validation_result import ValidationResult


def test_carries_deviation_and_defaults_detail_to_empty():
    # Arrange / Act
    result = ValidationResult(deviation=0.25)

    # Assert
    assert result.deviation == 0.25
    assert result.detail == ""


def test_carries_detail_when_given():
    # Arrange / Act
    result = ValidationResult(deviation=0.1, detail="dropped section 3")

    # Assert
    assert result.detail == "dropped section 3"
