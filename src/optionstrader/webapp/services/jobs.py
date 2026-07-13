"""In-process background jobs for the long-running commands (backtest, daily,
scan, squeeze, screen). Stdlib-only.

Deliberately minimal: uuid + daemon thread + status dict. Results live in
memory and are lost on server restart — acceptable for a single-user localhost
tool; the UI states this. `executor="sync"` runs the function inline on the
calling thread, giving tests a deterministic path with no polling races.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class Job:
    id: str
    kind: str
    label: str
    status: str = "running"          # running | done | error
    started: datetime = field(default_factory=datetime.now)
    finished: datetime | None = None
    result: Any = None
    error: str | None = None

    @property
    def elapsed(self) -> float:
        end = self.finished or datetime.now()
        return (end - self.started).total_seconds()


class JobRegistry:
    def __init__(self, keep: int = 20, executor: str = "thread"):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._keep = keep
        self._executor = executor

    def submit(self, kind: str, label: str, fn: Callable[[], Any]) -> str:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, label=label)
        with self._lock:
            self._jobs[job.id] = job
            self._prune()

        def run() -> None:
            try:
                job.result = fn()
                job.status = "done"
            except Exception as e:  # noqa: BLE001 — surfaced on the jobs page
                job.error = f"{type(e).__name__}: {e}"
                job.status = "error"
            finally:
                job.finished = datetime.now()

        if self._executor == "sync":
            run()
        else:
            threading.Thread(target=run, daemon=True, name=f"job-{job.kind}-{job.id}").start()
        return job.id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.started, reverse=True)

    def _prune(self) -> None:
        finished = [j for j in self._jobs.values() if j.status != "running"]
        excess = len(finished) - self._keep
        if excess > 0:
            for j in sorted(finished, key=lambda j: j.started)[:excess]:
                del self._jobs[j.id]
