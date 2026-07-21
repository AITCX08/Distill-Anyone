"""Bounded 3/1/3 pipeline with per-item failure isolation and durable state."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from src.application.events import EventHub
from src.asr.funasr_engine import load_transcript
from src.clean.text_processor import load_cleaned
from src.distillation.artifacts import ArtifactRecord, sha256_file
from src.distillation.processors import safe_cleanup_media
from src.distillation.request import DistillationRequest
from src.distillation.state import (
    ItemState,
    JobState,
    ProcessingStatus,
    recover_item,
    utc_now_iso,
)
from src.distillation.store import JobStateStore
from src.distillation.supervisor import WorkerSupervisor
from src.model.knowledge_extractor import load_video_knowledge
from src.outputs.base import ArtifactKind, CorpusOutputContext, ItemOutputContext
from src.platforms.models import DownloadedAssets, ItemType, SourceItem


_STOP = object()


@dataclass(frozen=True)
class JobResult:
    job_id: str
    total: int
    completed: int
    failed: int
    unsupported: int
    paused: bool = False


@dataclass(frozen=True)
class _PreparedWork:
    item: SourceItem
    prepared: Any


@dataclass(frozen=True)
class _TranscriptWork:
    item: SourceItem
    prepared: Any
    transcript: Any


def _record(path: Any) -> ArtifactRecord | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    return ArtifactRecord(
        path=str(candidate),
        sha256=sha256_file(candidate),
        size_bytes=candidate.stat().st_size,
        valid=True,
    )


class DistillationEngine:
    def __init__(
        self,
        *,
        adapter: Any,
        processor_factory: Callable[[], Any],
        state_store: JobStateStore,
        output_manager: Any | None = None,
        events: EventHub | None = None,
        supervisor: WorkerSupervisor | None = None,
    ) -> None:
        self.adapter = adapter
        self.processor_factory = processor_factory
        self.state_store = state_store
        self.output_manager = output_manager
        self.events = events or EventHub()
        self.supervisor = supervisor or WorkerSupervisor()
        self.state: JobState | None = None
        self._state_lock = asyncio.Lock()
        self._pause_requested = False
        self._processor = None
        self._contexts: dict[str, ItemOutputContext] = {}
        self._items: dict[str, SourceItem] = {}

    def request_pause(self) -> None:
        self._pause_requested = True

    async def _invoke(self, function: Callable, *args, **kwargs):
        if inspect.iscoroutinefunction(function):
            return await function(*args, **kwargs)
        return await asyncio.to_thread(function, *args, **kwargs)

    async def _initialize_state(self, request: DistillationRequest) -> None:
        existing = self.state_store.load() if self.state_store.path.exists() else None
        items = dict(existing.items) if existing is not None else {}
        for item in request.items:
            prior = items.get(item.source_id)
            items[item.source_id] = (
                recover_item(prior)
                if prior is not None
                else ItemState(
                    source_id=item.source_id,
                    processing_status=ProcessingStatus.ENUMERATED,
                )
            )
        base = existing or JobState(job_id=request.job_id)
        state = replace(
            base,
            job_id=request.job_id,
            status="running",
            request={
                "download_workers": request.download_workers,
                "asr_workers": request.asr_workers,
                "llm_workers": request.llm_workers,
                "max_active_items": request.max_active_items,
            },
            creator=asdict(request.creator),
            items=items,
        )
        self.state = self.state_store.save(
            state,
            expected_revision=existing.revision if existing is not None else None,
        )

    async def _update_item(self, source_id: str, **changes) -> ItemState:
        async with self._state_lock:
            item = self.state.items[source_id]
            updated_item = replace(item, updated_at=utc_now_iso(), **changes)
            items = dict(self.state.items)
            items[source_id] = updated_item
            self.state = self.state_store.save(
                replace(self.state, items=items),
                expected_revision=self.state.revision,
            )
        self.events.publish(
            "job.item.updated",
            {
                "job_id": self.state.job_id,
                "source_id": source_id,
                "processing_status": updated_item.processing_status.value,
                "revision": self.state.revision,
            },
        )
        return updated_item

    async def _stage_call(
        self,
        item: SourceItem,
        stage: str,
        status: ProcessingStatus,
        function: Callable,
        *args,
        retry_limit: int,
        **kwargs,
    ):
        for attempt in range(retry_limit + 1):
            current = self.state.items[item.source_id]
            attempts = dict(current.attempts)
            attempts[stage] = attempts.get(stage, 0) + 1
            await self._update_item(
                item.source_id,
                processing_status=status,
                attempts=attempts,
                last_error=None,
            )
            try:
                return await self._invoke(function, *args, **kwargs)
            except Exception:
                if attempt >= retry_limit:
                    raise

    async def _fail(self, item: SourceItem, error: Exception) -> None:
        await self._update_item(
            item.source_id,
            processing_status=ProcessingStatus.FAILED,
            last_error=str(error),
            completed_at=None,
        )

    async def _download_worker(
        self,
        request: DistillationRequest,
        queue: asyncio.Queue,
        asr_queue: asyncio.Queue,
        active: asyncio.Semaphore,
    ) -> None:
        while True:
            item = await queue.get()
            try:
                if item is _STOP:
                    return
                if self._pause_requested:
                    continue
                await active.acquire()
                try:
                    assets = await self._stage_call(
                        item,
                        "download",
                        ProcessingStatus.DOWNLOADING,
                        self.adapter.download_assets,
                        item,
                        request.output_root / "media",
                        progress=lambda value: self.events.publish(
                            "transfer.updated",
                            {
                                "job_id": request.job_id,
                                "source_id": item.source_id,
                                "progress": value,
                            },
                        ),
                        retry_limit=request.retry_limit,
                    )
                    prepared = await self._invoke(self._processor.prepare, item, assets)
                    artifacts = dict(self.state.items[item.source_id].artifacts)
                    for name, path in (
                        ("video", getattr(assets, "video_path", None)),
                        ("audio", getattr(assets, "audio_path", None)),
                    ):
                        record = _record(path)
                        if record:
                            artifacts[name] = record
                    await self._update_item(
                        item.source_id,
                        processing_status=ProcessingStatus.DOWNLOADED,
                        artifacts=artifacts,
                    )
                    await asr_queue.put(_PreparedWork(item, prepared))
                except Exception as exc:
                    await self._fail(item, exc)
                    active.release()
            finally:
                queue.task_done()

    async def _asr_worker(
        self,
        request: DistillationRequest,
        queue: asyncio.Queue,
        llm_queue: asyncio.Queue,
        active: asyncio.Semaphore,
    ) -> None:
        while True:
            work = await queue.get()
            try:
                if work is _STOP:
                    return
                try:
                    transcript = await self._stage_call(
                        work.item,
                        "asr",
                        ProcessingStatus.TRANSCRIBING,
                        self._processor.transcribe,
                        work.prepared,
                        retry_limit=request.retry_limit,
                    )
                    artifacts = dict(self.state.items[work.item.source_id].artifacts)
                    record = _record(getattr(transcript, "path", None))
                    if record:
                        artifacts["transcript"] = record
                    await self._update_item(
                        work.item.source_id,
                        processing_status=ProcessingStatus.CLEANING,
                        artifacts=artifacts,
                        transcript_verified=record is not None,
                    )
                    await llm_queue.put(_TranscriptWork(work.item, work.prepared, transcript))
                except Exception as exc:
                    await self._fail(work.item, exc)
                    active.release()
            finally:
                queue.task_done()

    async def _llm_worker(
        self,
        request: DistillationRequest,
        queue: asyncio.Queue,
        active: asyncio.Semaphore,
    ) -> None:
        while True:
            work = await queue.get()
            try:
                if work is _STOP:
                    return
                try:
                    enriched = await self._stage_call(
                        work.item,
                        "llm",
                        ProcessingStatus.SUMMARIZING,
                        self._processor.enrich,
                        work.transcript,
                        retry_limit=request.retry_limit,
                    )
                    artifacts = dict(self.state.items[work.item.source_id].artifacts)
                    for name, path in (
                        ("cleaned", getattr(enriched, "cleaned_path", None)),
                        ("knowledge", getattr(enriched, "knowledge_path", None)),
                    ):
                        record = _record(path)
                        if record:
                            artifacts[name] = record

                    context = ItemOutputContext(
                        item=work.item,
                        creator=request.creator,
                        output_root=request.output_root,
                        artifacts={
                            ArtifactKind.TRANSCRIPT: getattr(
                                work.transcript,
                                "document",
                                work.transcript,
                            ),
                            ArtifactKind.CLEANED: enriched.cleaned,
                            ArtifactKind.KNOWLEDGE: enriched.knowledge,
                        },
                        processed_at=datetime.now(timezone.utc),
                        processing_status="completed",
                    )
                    output_states = dict(self.state.items[work.item.source_id].outputs)
                    if self.output_manager is not None:
                        receipts = await self._invoke(self.output_manager.consume_item, context)
                        for receipt in receipts:
                            output_states[receipt.target] = {
                                "status": "completed",
                                "path": str(receipt.path),
                                "fingerprint": receipt.fingerprint,
                                "skipped": receipt.skipped,
                            }
                    self._contexts[work.item.source_id] = context

                    cleaned_media = False
                    if request.cleanup_media:
                        transcript_path = getattr(work.transcript, "path", None)
                        if transcript_path:
                            media_paths = {
                                getattr(work.prepared, "audio_path", None),
                                getattr(work.prepared.assets, "audio_path", None),
                                getattr(work.prepared.assets, "video_path", None),
                            }
                            outcomes = [
                                safe_cleanup_media(Path(path), transcript_path=Path(transcript_path))
                                for path in media_paths
                                if path is not None
                            ]
                            cleaned_media = bool(outcomes) and all(outcomes)
                    await self._update_item(
                        work.item.source_id,
                        processing_status=ProcessingStatus.COMPLETED,
                        artifacts=artifacts,
                        outputs=output_states,
                        temporary_media_cleaned=cleaned_media,
                        completed_at=utc_now_iso(),
                        stage_progress=1.0,
                        overall_progress=1.0,
                    )
                except Exception as exc:
                    await self._fail(work.item, exc)
                finally:
                    active.release()
            finally:
                queue.task_done()

    async def _finalize_outputs(self, request: DistillationRequest) -> None:
        if self.output_manager is None:
            return
        for item in request.items:
            if item.source_id in self._contexts:
                continue
            item_state = self.state.items[item.source_id]
            if item_state.processing_status is not ProcessingStatus.COMPLETED:
                continue
            required = ("transcript", "cleaned", "knowledge")
            if not all(name in item_state.artifacts for name in required):
                continue
            try:
                context = ItemOutputContext(
                    item=item,
                    creator=request.creator,
                    output_root=request.output_root,
                    artifacts={
                        ArtifactKind.TRANSCRIPT: load_transcript(
                            Path(item_state.artifacts["transcript"].path)
                        ),
                        ArtifactKind.CLEANED: load_cleaned(
                            Path(item_state.artifacts["cleaned"].path)
                        ),
                        ArtifactKind.KNOWLEDGE: load_video_knowledge(
                            Path(item_state.artifacts["knowledge"].path)
                        ),
                    },
                    processed_at=datetime.now(timezone.utc),
                    processing_status="completed",
                )
            except (OSError, ValueError, TypeError, KeyError):
                continue
            self._contexts[item.source_id] = context
            await self._invoke(self.output_manager.consume_item, context)

        items = tuple(self._contexts.values())
        counts = self._counts()
        if len(items) < counts[0]:
            self.events.publish(
                "job.output.deferred",
                {
                    "job_id": request.job_id,
                    "reason": "completed artifacts could not be reopened",
                },
            )
            return
        previous = {
            name: str(value.get("fingerprint", ""))
            for name, value in self.state.outputs.items()
            if isinstance(value, dict)
        }
        context = CorpusOutputContext(
            creator=request.creator,
            output_root=request.output_root,
            items=items,
            previous_fingerprints=previous,
            total_items=len(request.items),
            completed_items=counts[0],
            failed_items=counts[1],
            unsupported_items=counts[2],
        )
        receipts = await self._invoke(self.output_manager.finalize, context)
        outputs = dict(self.state.outputs)
        for receipt in receipts:
            outputs[receipt.target] = {
                "path": str(receipt.path),
                "fingerprint": receipt.fingerprint,
                "skipped": receipt.skipped,
                "metadata": dict(receipt.metadata),
            }
        async with self._state_lock:
            self.state = self.state_store.save(
                replace(self.state, outputs=outputs),
                expected_revision=self.state.revision,
            )

    def _counts(self) -> tuple[int, int, int]:
        states = self.state.items.values()
        completed = sum(item.processing_status is ProcessingStatus.COMPLETED for item in states)
        failed = sum(item.processing_status is ProcessingStatus.FAILED for item in states)
        unsupported = sum(item.processing_status is ProcessingStatus.UNSUPPORTED for item in states)
        return completed, failed, unsupported

    async def _queue_resumable_item(
        self,
        item: SourceItem,
        item_state: ItemState,
        active: asyncio.Semaphore,
        asr_queue: asyncio.Queue,
        llm_queue: asyncio.Queue,
    ) -> bool:
        transcript_record = item_state.artifacts.get("transcript")
        load_transcript = getattr(self._processor, "load_transcript_artifact", None)
        if (
            item_state.processing_status
            in {
                ProcessingStatus.CLEANING,
                ProcessingStatus.SUMMARIZING,
                ProcessingStatus.WRITING,
            }
            and transcript_record is not None
            and load_transcript is not None
        ):
            await active.acquire()
            transcript = await self._invoke(
                load_transcript,
                item,
                Path(transcript_record.path),
            )
            prepared = SimpleNamespace(
                item=item,
                audio_path=None,
                assets=DownloadedAssets(),
            )
            await llm_queue.put(_TranscriptWork(item, prepared, transcript))
            return True

        restore = getattr(self._processor, "restore_prepared", None)
        has_media = "audio" in item_state.artifacts or "video" in item_state.artifacts
        if (
            item_state.processing_status
            in {
                ProcessingStatus.DOWNLOADED,
                ProcessingStatus.EXTRACTING_AUDIO,
                ProcessingStatus.TRANSCRIBING,
            }
            and has_media
            and restore is not None
        ):
            await active.acquire()
            prepared = await self._invoke(restore, item, dict(item_state.artifacts))
            await asr_queue.put(_PreparedWork(item, prepared))
            return True
        return False

    async def run(self, request: DistillationRequest) -> JobResult:
        self._pause_requested = False
        self._state_lock = asyncio.Lock()
        self._processor = self.processor_factory()
        self._items = {item.source_id: item for item in request.items}
        await self._initialize_state(request)

        download_queue = asyncio.Queue(maxsize=request.download_workers * 2)
        asr_queue = asyncio.Queue(maxsize=max(2, request.max_active_items))
        llm_queue = asyncio.Queue(maxsize=request.llm_workers * 2)
        active = asyncio.Semaphore(request.max_active_items)

        download_tasks = [
            asyncio.create_task(
                self.supervisor.run(
                    f"download-{index}",
                    lambda q=download_queue: self._download_worker(request, q, asr_queue, active),
                )
            )
            for index in range(request.download_workers)
        ]
        asr_task = asyncio.create_task(
            self.supervisor.run(
                "asr-0",
                lambda: self._asr_worker(request, asr_queue, llm_queue, active),
            )
        )
        llm_tasks = [
            asyncio.create_task(
                self.supervisor.run(
                    f"llm-{index}",
                    lambda q=llm_queue: self._llm_worker(request, q, active),
                )
            )
            for index in range(request.llm_workers)
        ]

        for item in request.items:
            item_state = self.state.items[item.source_id]
            if item_state.processing_status is ProcessingStatus.COMPLETED:
                continue
            if item.item_type is not ItemType.VIDEO:
                await self._update_item(
                    item.source_id,
                    processing_status=ProcessingStatus.UNSUPPORTED,
                    last_error="unsupported_note: Gallery OCR is not enabled",
                )
                continue
            if await self._queue_resumable_item(
                item,
                item_state,
                active,
                asr_queue,
                llm_queue,
            ):
                continue
            await download_queue.put(item)
        for _ in download_tasks:
            await download_queue.put(_STOP)
        await asyncio.gather(*download_tasks)

        await asr_queue.put(_STOP)
        await asr_task

        for _ in llm_tasks:
            await llm_queue.put(_STOP)
        await asyncio.gather(*llm_tasks)

        await self._finalize_outputs(request)
        completed, failed, unsupported = self._counts()
        paused = self._pause_requested
        if paused:
            status = "paused"
        elif failed or unsupported:
            status = "partial" if completed else "failed"
        else:
            status = "completed"
        async with self._state_lock:
            self.state = self.state_store.save(
                replace(self.state, status=status),
                expected_revision=self.state.revision,
            )
        self.events.publish(
            "job.updated",
            {
                "job_id": request.job_id,
                "status": status,
                "revision": self.state.revision,
            },
        )
        return JobResult(
            job_id=request.job_id,
            total=len(request.items),
            completed=completed,
            failed=failed,
            unsupported=unsupported,
            paused=paused,
        )
