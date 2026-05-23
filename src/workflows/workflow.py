"""Workflow interface for book processing pipelines."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from src.config.feature_flags import FeatureFlags
from src.domain.models import Book


@dataclass(frozen=True)
class WorkflowRequest:
    """Input value object for ``Workflow.run``.

    Every workflow accepts the same request. Each workflow uses only the
    fields it needs. Staged workflows derive ``book_id`` from ``url``.

    Attributes:
        url: Project Gutenberg book URL. The only required field.
        start_chapter: 1-based inclusive index of the first chapter to parse.
        end_chapter: 1-based inclusive index of the last chapter to parse.
            ``None`` means parse to the end of the book.
        refresh: When ``True``, bypass any cached state and re-run from scratch.
        feature_flags: Deterministic pipeline toggles. Workflows that don't
            consume flags ignore this field.
    """

    url: str
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)


class Workflow(ABC):
    """Abstract workflow interface.

    A workflow orchestrates multiple components to process a book.

    All concrete workflows return a ``Book``. Any workflow-specific data
    (e.g. ``CharacterRegistry``) is carried as a field on the returned
    ``Book`` instance.
    """

    @abstractmethod
    def run(self, request: WorkflowRequest) -> Book:
        """Run the workflow with the given request.

        Args:
            request: Workflow input value object. See :class:`WorkflowRequest`.

        Returns:
            A fully populated Book instance.

        Raises:
            Exception: If the workflow fails.
        """
        pass
