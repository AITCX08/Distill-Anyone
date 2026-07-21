import asyncio

import pytest

from src.distillation.supervisor import SupervisorExhausted, WorkerSupervisor


def test_supervisor_restarts_worker_within_budget():
    calls = 0

    async def worker():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("crash")

    supervisor = WorkerSupervisor(restart_budget=2)

    asyncio.run(supervisor.run("worker", worker))

    assert calls == 3
    assert supervisor.restart_counts["worker"] == 2


def test_supervisor_raises_after_restart_budget():
    async def worker():
        raise RuntimeError("always crashes")

    with pytest.raises(SupervisorExhausted):
        asyncio.run(WorkerSupervisor(restart_budget=1).run("worker", worker))
