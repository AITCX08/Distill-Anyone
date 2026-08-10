"""Validation for the bounded, redacted JSONL worker event protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from src.application.redaction import redact_value

MAX_EVENT_BYTES = 16 * 1024
SUPPORTED_STAGES = frozenset(
    {
        "pending",
        "downloading",
        "downloaded",
        "extracting_audio",
        "transcribing",
        "cleaning",
        "summarizing",
        "writing",
        "completed",
        "paused",
        "failed",
        "cancelled",
    }
)
TERMINAL_STATUSES = frozenset({"completed", "failed", "paused", "cancelled", "interrupted"})
SUPPORTED_EVENT_TYPES = frozenset({"stage", "transfer", "checkpoint", "log", "terminal"})


class ProtocolError(ValueError):
    """Raised when a worker emits an unsafe or malformed event."""


@dataclass(frozen=True)
class WorkerEvent:
    kind: str
    task_id: str
    payload: Mapping[str, Any]


def parse_worker_event(line: str, expected_task_id: str) -> WorkerEvent:
    """Parse one worker JSONL line without allowing it to escape its task boundary."""

    if len(line.encode("utf-8")) > MAX_EVENT_BYTES:
        raise ProtocolError("worker event exceeds maximum size")
    try:
        raw = json.loads(line)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProtocolError("worker event is not valid JSON") from error
    if not isinstance(raw, dict):
        raise ProtocolError("worker event must be an object")
    if raw.get("v") != 1:
        raise ProtocolError("unsupported worker protocol version")
    kind = raw.get("type")
    if kind not in SUPPORTED_EVENT_TYPES:
        raise ProtocolError("unsupported worker event type")
    task_id = raw.get("task_id")
    if not isinstance(task_id, str) or task_id != expected_task_id:
        raise ProtocolError("worker event task does not match lease")

    _validate_payload(kind, raw)
    payload = {name: value for name, value in raw.items() if name not in {"v", "type", "task_id"}}
    return WorkerEvent(kind=kind, task_id=task_id, payload=redact_value(payload))


def _validate_payload(kind: str, raw: Mapping[str, Any]) -> None:
    if kind == "stage":
        _validate_stage(raw.get("stage"))
    elif kind == "transfer":
        completed = _nonnegative_measurement(raw, "completed_bytes")
        total = _nonnegative_measurement(raw, "total_bytes")
        _nonnegative_measurement(raw, "bytes_per_second")
        if completed > total:
            raise ProtocolError("completed_bytes cannot exceed total_bytes")
    elif kind == "checkpoint":
        _validate_stage(raw.get("stage"))
        _nonnegative_measurement(raw, "checkpoint_revision")
    elif kind == "log":
        if not isinstance(raw.get("line"), str):
            raise ProtocolError("log event requires text line")
    elif kind == "terminal":
        if raw.get("status") not in TERMINAL_STATUSES:
            raise ProtocolError("terminal event has invalid status")


def _validate_stage(stage: Any) -> None:
    if stage not in SUPPORTED_STAGES:
        raise ProtocolError("worker event has unknown stage")


def _nonnegative_measurement(raw: Mapping[str, Any], field: str) -> int | float:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ProtocolError(f"{field} must be a non-negative number")
    return value
