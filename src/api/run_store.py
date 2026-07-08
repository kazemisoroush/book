"""Persist run status through the Storage abstraction, shared by the API and worker Lambdas."""
import json
from dataclasses import asdict
from typing import Optional

from src.api.runner import RunStatus
from src.storage.storage import Storage

_RUNS_PREFIX = ".runs"
_STATUS_FILENAME = "status.json"


class RunStore:
    """Reads and writes run status under ``.runs/{run_id}/`` so both Lambdas share it."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def write_status(self, status: RunStatus) -> None:
        """Persist *status* for its run."""
        self._storage.write_text(
            _status_key(status.run_id), json.dumps(asdict(status), indent=2),
        )

    def read_status(self, run_id: str) -> Optional[RunStatus]:
        """Read the recorded status for *run_id*, or None if there is none."""
        key = _status_key(run_id)
        if not self._storage.exists(key):
            return None
        return RunStatus(**json.loads(self._storage.read_text(key)))


def _status_key(run_id: str) -> str:
    return f"{_RUNS_PREFIX}/{run_id}/{_STATUS_FILENAME}"
