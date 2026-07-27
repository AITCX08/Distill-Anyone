"""Bounded restart supervisor for long-running stage workers."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable


class SupervisorExhausted(RuntimeError):
    def __init__(self, worker_name: str, restarts: int):
        super().__init__(f"Worker {worker_name} exhausted restart budget after {restarts} restarts")
        self.worker_name = worker_name
        self.restarts = restarts


class WorkerSupervisor:
    def __init__(self, restart_budget: int = 2):
        if restart_budget < 0:
            raise ValueError("restart_budget cannot be negative")
        self.restart_budget = restart_budget
        self.restart_counts: dict[str, int] = defaultdict(int)

    async def run(
        self,
        worker_name: str,
        worker_factory: Callable[[], Awaitable[None]],
    ) -> None:
        while True:
            try:
                await worker_factory()
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.restart_counts[worker_name] >= self.restart_budget:
                    raise SupervisorExhausted(
                        worker_name,
                        self.restart_counts[worker_name],
                    ) from exc
                self.restart_counts[worker_name] += 1
