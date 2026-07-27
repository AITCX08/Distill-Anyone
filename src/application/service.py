"""Facade consumed identically by the CLI and local Dashboard."""

from __future__ import annotations

from typing import Any, Callable

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
        source_runner: Any | None = None,
        platform_manager: Any | None = None,
    ) -> None:
        self.repository = repository
        self.events = events or EventHub()
        self.commands = JobCommands(repository, self.events, previewer=previewer)
        self.queries = JobQueries(repository)
        self.source_runner = source_runner
        self.platform_manager = platform_manager or getattr(source_runner, "platform_manager", None)

    def run_source(self, request):
        if self.source_runner is None:
            raise RuntimeError("No creator source runner is configured")
        return self.source_runner.run(request)

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

    def list_platforms(self):
        if self.platform_manager is None:
            return ()
        return tuple(
            (descriptor, self.platform_manager.get(descriptor.name).auth_status())
            for descriptor in self.platform_manager.list_descriptors()
        )

    def login_platform(self, platform: str, *, headful: bool = True) -> None:
        if self.platform_manager is None:
            raise RuntimeError("No platform manager is configured")
        self.platform_manager.get(platform).authenticate(headful=headful)
