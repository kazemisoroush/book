"""Rich return type for Validator checks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """Measurement from a validator: a deviation and an optional detail."""
    deviation: float
    detail: str = ""
