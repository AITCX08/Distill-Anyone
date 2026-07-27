"""Facade consumed identically by the CLI and local Dashboard."""

from __future__ import annotations

from dataclasses import replace
from threading import Thread
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
        resolved_previewer = previewer or getattr(source_runner, "preview", None)
        self.commands = JobCommands(repository, self.events, previewer=resolved_previewer)
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
        preview = self.preview(request.preview_request())
        job_id_for_preview = getattr(self.source_runner, "job_id_for_preview", None)
        if callable(job_id_for_preview):
            request = replace(request, job_id=job_id_for_preview(preview))
        created = self.commands.create(request)
        if self.source_runner is not None:
            from src.application.source_runner import SourceCreatorRequest

            source_request = SourceCreatorRequest(
                target=request.target,
                platform=request.platform,
                emit=request.outputs,
                rag_chunks=request.rag_chunks,
            )
            Thread(
                target=self._run_created_source,
                args=(created.job_id, source_request),
                daemon=True,
                name=f"distill-source-{created.job_id[:12]}",
            ).start()
        return created

    def _run_created_source(self, job_id: str, request: Any) -> None:
        try:
            self.run_source(request)
        except Exception:
            store = self.repository.store(job_id)
            current = store.load()
            saved = store.save(
                replace(current, status=JobStatus.FAILED.value),
                expected_revision=current.revision,
            )
            self.events.publish(
                "job.updated",
                {"job_id": job_id, "status": saved.status, "revision": saved.revision},
            )

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
