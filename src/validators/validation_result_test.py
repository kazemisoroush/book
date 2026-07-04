"""Tests for ValidationResult threshold semantics."""
from src.validators.validation_result import ValidationResult


def test_default_threshold_is_strict():
    # Arrange / Act
    exact = ValidationResult(deviation=0.0)
    drifted = ValidationResult(deviation=0.001)

    # Assert
    assert exact.passed
    assert not drifted.passed


def test_deviation_within_threshold_passes():
    # Arrange / Act
    result = ValidationResult(deviation=0.03, threshold=0.05)

    # Assert
    assert result.passed


def test_deviation_above_threshold_fails():
    # Arrange / Act
    result = ValidationResult(deviation=0.06, threshold=0.05)

    # Assert
    assert not result.passed


def test_deviation_equal_to_threshold_passes():
    # Arrange / Act
    result = ValidationResult(deviation=0.05, threshold=0.05)

    # Assert
    assert result.passed
