"""Workflow factory for creating workflow instances."""
from pathlib import Path
from typing import Callable

from src.repository.file_book_repository import FileBookRepository

from .ai_workflow import AIProjectGutenbergWorkflow
from .ambient_workflow import AmbientWorkflow
from .mix_workflow import MixWorkflow
from .music_workflow import MusicWorkflow
from .sfx_workflow import SfxWorkflow
from .tts_workflow import TTSWorkflow
from .workflow import Workflow

WorkflowBuilder = Callable[[Path], Workflow]

# Registry of workflow builders keyed by CLI name. To add a new workflow,
# register its builder here; create_workflow() stays closed for modification
# (open/closed principle).
_WORKFLOW_BUILDERS: dict[str, WorkflowBuilder] = {
    "ai": lambda books_dir: AIProjectGutenbergWorkflow.create(
        repository=FileBookRepository(base_dir=str(books_dir)),
    ),
    "tts": lambda books_dir: TTSWorkflow.create(books_dir=books_dir),
    "ambient": lambda books_dir: AmbientWorkflow.create(books_dir=books_dir),
    "sfx": lambda books_dir: SfxWorkflow.create(books_dir=books_dir),
    "music": lambda books_dir: MusicWorkflow.create(books_dir=books_dir),
    "mix": lambda books_dir: MixWorkflow.create(books_dir=books_dir),
}


def create_workflow(workflow_name: str, books_dir: Path = Path("books")) -> Workflow:
    """Create a workflow instance by name.

    Args:
        workflow_name: Name of the workflow to create (ai, tts, ambient, sfx, music, mix).
        books_dir: Base directory for book output (default: books/).

    Returns:
        A fully-wired Workflow instance.

    Raises:
        ValueError: If workflow_name is not registered.
    """
    try:
        builder = _WORKFLOW_BUILDERS[workflow_name]
    except KeyError as exc:
        raise ValueError(f"Unknown workflow: {workflow_name}") from exc
    return builder(books_dir)
