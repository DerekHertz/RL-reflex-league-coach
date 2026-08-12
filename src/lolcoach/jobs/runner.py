"""In-memory background job runner with SSE-friendly progress streaming.

Not Celery/Redis -- unambiguously over-engineered for a single dev-key,
single-process app. Not persisted to SQLite either: if the process restarts
mid-job the job is lost, which is an acceptable tradeoff for a local
single-user app (revisit if this ever needs to survive restarts).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class JobEvent:
    stage: str
    progress: float  # 0.0..1.0
    message: str
    status: JobStatus
    result: Any | None = None
    error: str | None = None


@dataclass
class _JobState:
    status: JobStatus = JobStatus.QUEUED
    latest: JobEvent | None = None
    result: Any | None = None
    error: str | None = None
    subscribers: list[asyncio.Queue[JobEvent]] = field(default_factory=list)


Emit = Callable[[str, float, str], None]


class JobRunner:
    def __init__(self, max_concurrent: int = 1) -> None:
        self._jobs: dict[str, _JobState] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def submit(self, work: Callable[[Emit], Awaitable[Any]]) -> str:
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = _JobState()
        task = asyncio.create_task(self._run(job_id, work))
        task.add_done_callback(_log_task_exception)
        return job_id

    async def _run(self, job_id: str, work: Callable[[Emit], Awaitable[Any]]) -> None:
        state = self._jobs[job_id]
        async with self._semaphore:
            state.status = JobStatus.RUNNING
            self._publish(job_id, JobEvent(stage="starting", progress=0.0, message="starting", status=JobStatus.RUNNING))

            def emit(stage: str, progress: float, message: str) -> None:
                self._publish(job_id, JobEvent(stage=stage, progress=progress, message=message, status=JobStatus.RUNNING))

            try:
                result = await work(emit)
                state.status = JobStatus.DONE
                state.result = result
                self._publish(job_id, JobEvent(stage="done", progress=1.0, message="done", status=JobStatus.DONE, result=result))
            except Exception as exc:  # noqa: BLE001 -- surfaced to subscribers, not swallowed
                message = f"{type(exc).__name__}: {exc}"
                state.status = JobStatus.ERROR
                state.error = message
                self._publish(job_id, JobEvent(stage="error", progress=1.0, message=message, status=JobStatus.ERROR, error=message))

    def _publish(self, job_id: str, event: JobEvent) -> None:
        state = self._jobs[job_id]
        state.latest = event
        for queue in state.subscribers:
            queue.put_nowait(event)

    def get_state(self, job_id: str) -> _JobState:
        if job_id not in self._jobs:
            raise KeyError(job_id)
        return self._jobs[job_id]

    async def subscribe(self, job_id: str) -> AsyncIterator[JobEvent]:
        if job_id not in self._jobs:
            raise KeyError(job_id)
        state = self._jobs[job_id]
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()
        if state.latest is not None:
            queue.put_nowait(state.latest)
        state.subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.status in (JobStatus.DONE, JobStatus.ERROR):
                    break
        finally:
            state.subscribers.remove(queue)


def _log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        import logging

        logging.getLogger(__name__).exception("job task failed outside _run's try/except", exc_info=exc)
