"""Rich return type for Validator checks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """Deviation between actual and expected output, with an optional detail."""
    deviation: float
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.deviation == 0.0
