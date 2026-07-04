"""Rich return type for Validator checks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """Deviation between actual and expected output, judged against a threshold."""
    deviation: float
    threshold: float = 0.0
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.deviation <= self.threshold
