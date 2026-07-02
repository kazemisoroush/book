"""Raised when a parsed chapter fails one or more validators."""


class ValidationGateError(Exception):
    """Signals that a chapter must not proceed past the validation gate."""

    def __init__(
        self, book_id: str, chapter_number: int, failures: dict[str, float],
    ) -> None:
        self.book_id = book_id
        self.chapter_number = chapter_number
        self.failures = failures
        details = ", ".join(
            f"{name} deviation={deviation:.4f}"
            for name, deviation in failures.items()
        )
        super().__init__(
            f"chapter {chapter_number} of {book_id} failed validation: {details}"
        )
