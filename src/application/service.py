"""Facade consumed identically by the CLI and local Dashboard."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from src.application.commands import (
    CreateJobRequest,
    JobCommands,
    JobStatus,
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

            self._start_source(
                created.job_id,
                SourceCreatorRequest(
                    target=request.target,
                    platform=request.platform,
                    emit=request.outputs,
                    rag_chunks=request.rag_chunks,
                    output_directory=Path(request.output_directory) if request.output_directory else None,
                ),
            )
        return created

    def _start_source(self, job_id: str, request: Any) -> None:
        Thread(
            target=self._run_created_source,
            args=(job_id, request),
            daemon=True,
            name=f"distill-source-{job_id[:12]}",
        ).start()

    def _source_request_from_state(self, job_id: str, *, retry_failed: bool = False):
        from src.application.source_runner import SourceCreatorRequest

        state = self.queries.get(job_id)
        values = state.request
        target = str(values.get("target") or state.creator.get("canonical_url") or "")
        if not target:
            raise RuntimeError("The job cannot be resumed because its source target is unavailable")
        return SourceCreatorRequest(
            target=target,
            platform=str(values.get("platform") or state.creator.get("platform") or "auto"),
            emit=tuple(values.get("outputs") or ("skill",)),
            rag_chunks=bool(values.get("rag_chunks", False)),
            download_workers=int(values.get("download_workers", 3)),
            asr_workers=int(values.get("asr_workers", 1)),
            llm_workers=int(values.get("llm_workers", 3)),
            max_active_items=int(values.get("max_active_items", 3)),
            retry_limit=int(values.get("retry_limit", 2)),
            resume=True,
            retry_failed=retry_failed,
            keep_media=bool(values.get("keep_media", False)),
            llm_provider=values.get("llm_provider"),
            output_directory=(Path(str(values["output_directory"])) if values.get("output_directory") else None),
        )

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
        paused = self.commands.pause(job_id, expected_revision)
        request_pause = getattr(self.source_runner, "request_pause", None)
        if callable(request_pause):
            request_pause(job_id)
        return paused

    def resume(self, job_id: str, expected_revision: int) -> JobView:
        resumed = self.commands.resume(job_id, expected_revision)
        if self.source_runner is not None:
            self._start_source(job_id, self._source_request_from_state(job_id))
        return resumed

    def retry_failed(self, job_id: str, expected_revision: int) -> JobView:
        retried = self.commands.retry_failed(job_id, expected_revision)
        if self.source_runner is not None:
            self._start_source(job_id, self._source_request_from_state(job_id, retry_failed=True))
        return retried

    def retry_item(self, job_id: str, source_id: str, expected_revision: int) -> JobView:
        retried = self.commands.retry_item(job_id, source_id, expected_revision)
        if self.source_runner is not None:
            self._start_source(job_id, self._source_request_from_state(job_id, retry_failed=True))
        return retried

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
