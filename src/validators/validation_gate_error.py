"""Raised when a parsed chapter fails one or more validators."""


class ValidationGateError(Exception):
    """Signals that a chapter must not proceed past the validation gate."""

    def __init__(
        self,
        book_id: str,
        chapter_number: int,
        failures: list[tuple[str, float, str]],
    ) -> None:
        self.book_id = book_id
        self.chapter_number = chapter_number
        self.failures = failures
        details = ", ".join(
            f"{name} deviation={deviation:.6g}" + (f" ({detail})" if detail else "")
            for name, deviation, detail in failures
        )
        super().__init__(
            f"chapter {chapter_number} of {book_id} failed validation: {details}"
        )
