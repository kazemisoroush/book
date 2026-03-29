"""Workflows package for orchestrating book processing pipelines."""
from src.workflows.workflow import Workflow
from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.workflows.tts_project_gutenberg_workflow import TTSProjectGutenbergWorkflow

__all__ = [
    "Workflow",
    "ProjectGutenbergWorkflow",
    "AIProjectGutenbergWorkflow",
    "TTSProjectGutenbergWorkflow",
]
