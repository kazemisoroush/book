"""Workflows package for orchestrating book processing pipelines."""
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow import Workflow

__all__ = [
    "Workflow",
    "ProjectGutenbergWorkflow",
    "AIProjectGutenbergWorkflow",
    "TTSWorkflow",
]
