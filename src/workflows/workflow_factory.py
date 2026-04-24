"""Workflow factory for creating workflow instances."""
from pathlib import Path

from src.repository.file_book_repository import FileBookRepository

from .ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from .ambient_workflow import AmbientWorkflow
from .mix_workflow import MixWorkflow
from .music_workflow import MusicWorkflow
from .project_gutenberg_workflow import ProjectGutenbergWorkflow
from .sfx_workflow import SfxWorkflow
from .tts_workflow import TTSWorkflow
from .workflow import Workflow


def create_workflow(workflow_name: str, books_dir: Path = Path("books")) -> Workflow:
    """Create a workflow instance by name.

    Args:
        workflow_name: Name of the workflow to create (parse, ai, tts, ambient, sfx, music, mix)
        books_dir: Base directory for book output (default: books/)

    Returns:
        A fully-wired Workflow instance

    Raises:
        ValueError: If workflow_name is not recognized
    """
    if workflow_name == "parse":
        return ProjectGutenbergWorkflow.create()
    elif workflow_name == "ai":
        repository = FileBookRepository(base_dir=str(books_dir))
        return AIProjectGutenbergWorkflow.create(repository=repository)
    elif workflow_name == "tts":
        return TTSWorkflow.create(books_dir=books_dir)
    elif workflow_name == "ambient":
        return AmbientWorkflow.create(books_dir=books_dir)
    elif workflow_name == "sfx":
        return SfxWorkflow.create(books_dir=books_dir)
    elif workflow_name == "music":
        return MusicWorkflow.create(books_dir=books_dir)
    elif workflow_name == "mix":
        return MixWorkflow.create(books_dir=books_dir)
    else:
        raise ValueError(f"Unknown workflow: {workflow_name}")
