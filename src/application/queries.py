"""Read-side repository and presentation-neutral job views."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from src.application.errors import JobAlreadyExistsError, JobNotFoundError
from src.distillation.state import JobState
from src.distillation.store import JobStateStore


class JobRepository:
    def __init__(self, root: Path):
        self.root = root
        self._paths: dict[str, Path] = {}

    def register(self, job_id: str, *, platform: str, creator_id: str) -> JobStateStore:
        platform_component = quote(platform, safe="-_.")
        creator_component = quote(creator_id, safe="-_.")
        path = self.root / platform_component / creator_component / "job_state.json"
        if path.exists():
            existing = JobStateStore(path).load()
            if existing.job_id != job_id:
                raise JobAlreadyExistsError(existing.job_id)
        self._paths[job_id] = path
        return JobStateStore(path)

    def store(self, job_id: str) -> JobStateStore:
        path = self._paths.get(job_id)
        if path is not None:
            return JobStateStore(path)
        if self.root.exists():
            for candidate in self.root.glob("*/*/job_state.json"):
                state = JobStateStore(candidate).load()
                self._paths[state.job_id] = candidate
                if state.job_id == job_id:
                    return JobStateStore(candidate)
        raise JobNotFoundError(job_id)

    def stores(self) -> tuple[JobStateStore, ...]:
        paths = set(self._paths.values())
        if self.root.exists():
            paths.update(self.root.glob("*/*/job_state.json"))
        return tuple(JobStateStore(path) for path in sorted(paths))


class JobQueries:
    def __init__(self, repository: JobRepository):
        self.repository = repository

    def get(self, job_id: str) -> JobState:
        return self.repository.store(job_id).load()

    def list(self) -> tuple[JobState, ...]:
        states = [store.load() for store in self.repository.stores()]
        return tuple(sorted(states, key=lambda state: state.updated_at, reverse=True))

    def items(self, job_id: str):
        return self.get(job_id).items

    def artifacts(self, job_id: str):
        state = self.get(job_id)
        return {
            source_id: item.artifacts
            for source_id, item in state.items.items()
            if item.artifacts
        }
