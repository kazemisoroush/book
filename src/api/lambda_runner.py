"""A runner that dispatches a workflow run to the worker Lambda and shares its state via storage.

Used in the cloud where the API cannot spawn a long-lived subprocess. It writes an initial
RUNNING status to the shared store, invokes the worker asynchronously, and the worker writes the
terminal status back to the same store.
"""
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from src.api.run_store import RunStore
from src.api.runner import RUNNING, RunParams, RunStatus
from src.storage.storage import Storage

_EVENT_PARAM_KEYS = ("start_chapter", "end_chapter", "refresh", "provider")


class LambdaWorkflowRunner:
    """Starts runs by invoking the worker Lambda and reads their status from shared storage."""

    def __init__(
        self,
        worker_function_name: str,
        storage: Storage,
        client: Optional[Any] = None,
    ) -> None:
        self._worker = worker_function_name
        self._store = RunStore(storage)
        self._client = client

    def start(self, workflow: str, params: RunParams) -> RunStatus:
        """Record a RUNNING status and invoke the worker to execute the run."""
        run_id = uuid.uuid4().hex
        status = RunStatus(
            run_id=run_id,
            workflow=workflow,
            params=asdict(params),
            state=RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._store.write_status(status)
        self._invoke({"run_id": run_id, "workflow": workflow, "url": params.url,
                       **{key: getattr(params, key) for key in _EVENT_PARAM_KEYS}})
        return status

    def status(self, run_id: str) -> Optional[RunStatus]:
        """Read the run's status from the shared store, or None if unknown."""
        return self._store.read_status(run_id)

    def read_logs(
        self, run_id: str, cursor: int = 0, flush: bool = False,
    ) -> tuple[list[str], int]:
        """Cloud run logs go to CloudWatch; live log streaming is a follow-up."""
        del run_id, flush
        return [], cursor

    def _invoke(self, event: dict[str, Any]) -> None:
        client = self._client
        if client is None:
            import boto3
            client = boto3.client("lambda")
        client.invoke(
            FunctionName=self._worker,
            InvocationType="Event",
            Payload=json.dumps(event).encode("utf-8"),
        )
