"""Rich return type for Validator checks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """Deviation between actual and expected output on a 0 to 1 scale."""
    deviation: float

    @property
    def passed(self) -> bool:
        return self.deviation == 0.0
