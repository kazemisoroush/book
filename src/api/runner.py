"""Runs CLI workflows as subprocesses and records their state on disk."""
import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"

_RUNS_DIRNAME = ".runs"
_STATUS_FILENAME = "status.json"
_LOG_FILENAME = "log.ndjson"


@dataclass
class RunParams:
    """Arguments forwarded to a single CLI workflow invocation."""
    url: str
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    provider: Optional[str] = None


@dataclass
class RunStatus:
    """On-disk record of one workflow run."""
    run_id: str
    workflow: str
    params: dict
    state: str
    pid: Optional[int] = None
    returncode: Optional[int] = None
    started_at: str = ""
    ended_at: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Whether the run has finished, successfully or not."""
        return self.state in (SUCCEEDED, FAILED)


class Runner(Protocol):
    """What the API needs from a runner, satisfied by the local and Lambda implementations."""

    def start(self, workflow: str, params: RunParams) -> RunStatus: ...

    def status(self, run_id: str) -> Optional[RunStatus]: ...

    def read_logs(
        self, run_id: str, cursor: int = 0, flush: bool = False,
    ) -> tuple[list[str], int]: ...


class WorkflowRunner:
    """Starts workflow subprocesses and exposes their status and logs as files."""

    def __init__(
        self,
        books_dir: Path,
        command_prefix: Optional[list[str]] = None,
        cwd: Optional[Path] = None,
    ) -> None:
        self._books_dir = Path(books_dir)
        self._command_prefix = command_prefix or [sys.executable, "main.py"]
        self._cwd = Path(cwd) if cwd is not None else Path.cwd()

    def start(self, workflow: str, params: RunParams) -> RunStatus:
        """Spawn the workflow subprocess and return its initial status."""
        run_id = uuid.uuid4().hex
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        command = self._build_command(workflow, params)
        log_path = run_dir / _LOG_FILENAME
        log_handle = log_path.open("w", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(self._cwd),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception:
            log_handle.close()
            raise

        status = RunStatus(
            run_id=run_id,
            workflow=workflow,
            params=asdict(params),
            state=RUNNING,
            pid=process.pid,
            started_at=_now(),
        )
        self._write_status(status)

        watcher = threading.Thread(
            target=self._wait_and_finalize,
            args=(process, log_handle, status),
            daemon=True,
        )
        watcher.start()
        return status

    def status(self, run_id: str) -> Optional[RunStatus]:
        """Read the recorded status for *run_id*, or None if unknown."""
        status_path = self._run_dir(run_id) / _STATUS_FILENAME
        if not status_path.exists():
            return None
        data = json.loads(status_path.read_text(encoding="utf-8"))
        return RunStatus(**data)

    def log_path(self, run_id: str) -> Path:
        """Return the log file path for *run_id*."""
        return self._run_dir(run_id) / _LOG_FILENAME

    def read_logs(
        self, run_id: str, cursor: int = 0, flush: bool = False,
    ) -> tuple[list[str], int]:
        """Return log lines from *cursor* onward and the next cursor as a line count."""
        log_path = self.log_path(run_id)
        if not log_path.exists():
            return [], cursor
        with log_path.open("r", encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        elif not flush:
            lines = lines[:-1]
        start = max(cursor, 0)
        new_lines = lines[start:]
        return new_lines, start + len(new_lines)

    def _build_command(self, workflow: str, params: RunParams) -> list[str]:
        command = [
            *self._command_prefix,
            "--workflow", workflow,
            "--url", params.url,
            "--start-chapter", str(params.start_chapter),
        ]
        if params.end_chapter is not None:
            command += ["--end-chapter", str(params.end_chapter)]
        if params.refresh:
            command.append("--refresh")
        if params.provider is not None:
            command += ["--provider", params.provider]
        return command

    def _wait_and_finalize(
        self,
        process: subprocess.Popen,
        log_handle,
        status: RunStatus,
    ) -> None:
        returncode = process.wait()
        log_handle.close()
        status.returncode = returncode
        status.state = SUCCEEDED if returncode == 0 else FAILED
        status.ended_at = _now()
        self._write_status(status)

    def _write_status(self, status: RunStatus) -> None:
        status_path = self._run_dir(status.run_id) / _STATUS_FILENAME
        temp_path = status_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(asdict(status), indent=2), encoding="utf-8",
        )
        os.replace(temp_path, status_path)

    def _run_dir(self, run_id: str) -> Path:
        return self._books_dir / _RUNS_DIRNAME / run_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
