"""Facade consumed identically by the CLI and local Dashboard."""

from __future__ import annotations

from typing import Callable

from src.application.commands import (
    CreateJobRequest,
    JobCommands,
    JobView,
    PreviewRequest,
    PreviewResult,
)
from src.application.events import EventHub
from src.application.queries import JobQueries, JobRepository


class DistillationService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        events: EventHub | None = None,
        previewer: Callable[[PreviewRequest], PreviewResult] | None = None,
    ) -> None:
        self.repository = repository
        self.events = events or EventHub()
        self.commands = JobCommands(repository, self.events, previewer=previewer)
        self.queries = JobQueries(repository)

    def preview(self, request: PreviewRequest) -> PreviewResult:
        return self.commands.preview(request)

    def create(self, request: CreateJobRequest) -> JobView:
        return self.commands.create(request)

    def get_job(self, job_id: str) -> JobView:
        return JobView.from_state(self.queries.get(job_id))

    def list_jobs(self) -> tuple[JobView, ...]:
        return tuple(JobView.from_state(state) for state in self.queries.list())

    def pause(self, job_id: str, expected_revision: int) -> JobView:
        return self.commands.pause(job_id, expected_revision)

    def resume(self, job_id: str, expected_revision: int) -> JobView:
        return self.commands.resume(job_id, expected_revision)

    def retry_failed(self, job_id: str, expected_revision: int) -> JobView:
        return self.commands.retry_failed(job_id, expected_revision)

    def retry_item(self, job_id: str, source_id: str, expected_revision: int) -> JobView:
        return self.commands.retry_item(job_id, source_id, expected_revision)
