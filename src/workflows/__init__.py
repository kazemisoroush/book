"""Workflows package for orchestrating book processing pipelines."""
from src.workflows.ai_workflow import AIProjectGutenbergWorkflow
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow import Workflow

__all__ = [
    "Workflow",
    "AIProjectGutenbergWorkflow",
    "TTSWorkflow",
]
