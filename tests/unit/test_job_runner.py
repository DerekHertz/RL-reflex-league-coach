import asyncio

import pytest

from lolcoach.jobs.runner import JobRunner, JobStatus


@pytest.mark.asyncio
async def test_job_runs_to_completion_and_reports_status() -> None:
    runner = JobRunner()

    async def work(emit) -> dict:
        emit("step1", 0.5, "halfway")
        return {"answer": 42}

    job_id = runner.submit(work)

    events = [event async for event in runner.subscribe(job_id)]
    assert events[-1].status == JobStatus.DONE
    assert events[-1].result == {"answer": 42}
    assert any(e.stage == "step1" for e in events)

    state = runner.get_state(job_id)
    assert state.status == JobStatus.DONE
    assert state.result == {"answer": 42}


@pytest.mark.asyncio
async def test_job_failure_is_captured_not_raised() -> None:
    runner = JobRunner()

    async def work(emit) -> dict:
        raise ValueError("boom")

    job_id = runner.submit(work)
    events = [event async for event in runner.subscribe(job_id)]

    assert events[-1].status == JobStatus.ERROR
    assert "boom" in events[-1].error

    state = runner.get_state(job_id)
    assert state.status == JobStatus.ERROR
    assert "ValueError" in state.error


@pytest.mark.asyncio
async def test_unknown_job_id_raises_key_error() -> None:
    runner = JobRunner()
    with pytest.raises(KeyError):
        runner.get_state("does-not-exist")
    with pytest.raises(KeyError):
        async for _ in runner.subscribe("does-not-exist"):
            pass


@pytest.mark.asyncio
async def test_late_subscriber_still_gets_terminal_event() -> None:
    # A subscriber that connects after the job already finished must still
    # see the terminal event (via `state.latest` seeding the new queue) --
    # this is the SSE "job finished before the browser connected" case.
    runner = JobRunner()

    async def work(emit) -> dict:
        return {"ok": True}

    job_id = runner.submit(work)
    # Let the job actually finish before subscribing.
    for _ in range(50):
        if runner.get_state(job_id).status == JobStatus.DONE:
            break
        await asyncio.sleep(0.01)

    events = [event async for event in runner.subscribe(job_id)]
    assert events[-1].status == JobStatus.DONE
