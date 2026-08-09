"""One-process-per-work pipeline runner with durable, local checkpoints."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.application.redaction import redact_value
from src.distillation.state import utc_now_iso


class Pipeline(Protocol):
    """The task-specific implementation of the full distillation pipeline."""


@dataclass(frozen=True)
class WorkerContext:
    task_id: str
    payload: Mapping[str, Any]
    work_dir: Path
    artifacts: Mapping[str, str]


_NEXT_STAGE = {
    "pending": ("download", "downloaded"),
    "downloading": ("download", "downloaded"),
    "downloaded": ("extract_audio", "transcribing"),
    "extracting_audio": ("extract_audio", "transcribing"),
    "transcribing": ("transcribe", "cleaning"),
    "cleaning": ("clean", "summarizing"),
    "summarizing": ("summarize", "writing"),
    "writing": ("write", "completed"),
}
_TERMINAL_STAGES = frozenset({"completed", "paused", "cancelled"})


def run_worker(task_id: str, payload_path: Path, *, pipeline: Pipeline | None = None) -> int:
    """Run or resume one work without creating or controlling sibling processes."""

    try:
        payload = _load_payload(payload_path, task_id)
        work_dir = Path(payload["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = _load_checkpoint(work_dir, task_id)
        artifacts = dict(checkpoint.get("artifacts", {}))

        while checkpoint["stage"] not in _TERMINAL_STAGES:
            action = _requested_action(work_dir)
            if action is not None:
                checkpoint = _write_checkpoint(
                    work_dir,
                    task_id,
                    stage="paused" if action == "pause" else "cancelled",
                    previous=checkpoint,
                    artifacts=artifacts,
                )
                _append_event(work_dir, task_id, "checkpoint", {
                    "stage": checkpoint["stage"],
                    "checkpoint_revision": checkpoint["checkpoint_revision"],
                })
                _append_event(work_dir, task_id, "terminal", {"status": checkpoint["stage"]})
                return 0

            step = _NEXT_STAGE.get(checkpoint["stage"])
            if step is None:
                raise RuntimeError("checkpoint has an unsupported stage")
            method_name, next_stage = step
            if pipeline is None:
                raise RuntimeError("worker pipeline implementation is unavailable")
            stage_method = getattr(pipeline, method_name, None)
            if stage_method is None:
                raise RuntimeError(f"worker pipeline cannot execute {method_name}")

            _append_event(work_dir, task_id, "stage", {"stage": checkpoint["stage"]})
            context = WorkerContext(task_id, payload, work_dir, dict(artifacts))
            produced = stage_method(context)
            if produced is not None:
                if not isinstance(produced, Mapping):
                    raise RuntimeError(f"{method_name} must return artifact mapping")
                artifacts.update(_relative_artifacts(produced))
            checkpoint = _write_checkpoint(
                work_dir,
                task_id,
                stage=next_stage,
                previous=checkpoint,
                artifacts=artifacts,
            )
            _append_event(work_dir, task_id, "checkpoint", {
                "stage": checkpoint["stage"],
                "checkpoint_revision": checkpoint["checkpoint_revision"],
            })

        _append_event(work_dir, task_id, "terminal", {"status": checkpoint["stage"]})
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        work_dir = _work_dir_or_none(payload_path)
        if work_dir is not None:
            _append_event(work_dir, task_id, "terminal", {"status": "failed", "reason": str(error)})
        return 1


def _load_payload(payload_path: Path, task_id: str) -> dict[str, Any]:
    value = json.loads(Path(payload_path).read_text("utf-8"))
    if not isinstance(value, dict) or value.get("task_id") != task_id:
        raise ValueError("payload task id does not match worker task")
    if not isinstance(value.get("work_dir"), str) or not value["work_dir"]:
        raise ValueError("payload work_dir is required")
    return value


def _work_dir_or_none(payload_path: Path) -> Path | None:
    try:
        value = json.loads(Path(payload_path).read_text("utf-8"))
        work_dir = value.get("work_dir") if isinstance(value, dict) else None
        return Path(work_dir) if isinstance(work_dir, str) and work_dir else None
    except (OSError, ValueError, TypeError):
        return None


def _load_checkpoint(work_dir: Path, task_id: str) -> dict[str, Any]:
    path = work_dir / "checkpoint.json"
    if not path.exists():
        return {
            "task_id": task_id,
            "stage": "pending",
            "checkpoint_revision": 0,
            "artifacts": {},
            "transcript_verified": False,
        }
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict) or value.get("task_id") != task_id:
        raise ValueError("checkpoint task id does not match worker task")
    if value.get("stage") not in {*_NEXT_STAGE, *_TERMINAL_STAGES}:
        raise ValueError("checkpoint stage is invalid")
    if not isinstance(value.get("checkpoint_revision"), int) or value["checkpoint_revision"] < 0:
        raise ValueError("checkpoint revision is invalid")
    artifacts = value.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("checkpoint artifacts are invalid")
    value["artifacts"] = _relative_artifacts(artifacts)
    return value


def _relative_artifacts(artifacts: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, reference in artifacts.items():
        if not isinstance(name, str) or not isinstance(reference, str):
            raise ValueError("artifact references must be strings")
        path = Path(reference)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact references must remain inside the worker directory")
        result[name] = reference
    return result


def _requested_action(work_dir: Path) -> str | None:
    path = work_dir / "control.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    action = value.get("action") if isinstance(value, dict) else None
    return action if action in {"pause", "cancel"} else None


def _write_checkpoint(
    work_dir: Path,
    task_id: str,
    *,
    stage: str,
    previous: Mapping[str, Any],
    artifacts: Mapping[str, str],
) -> dict[str, Any]:
    checkpoint = {
        "task_id": task_id,
        "stage": stage,
        "checkpoint_revision": int(previous["checkpoint_revision"]) + 1,
        "artifacts": dict(artifacts),
        "transcript_verified": bool(previous.get("transcript_verified", False)),
        "updated_at": utc_now_iso(),
    }
    destination = work_dir / "checkpoint.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True), "utf-8")
    os.replace(temporary, destination)
    return checkpoint


def _append_event(work_dir: Path, task_id: str, kind: str, payload: Mapping[str, Any]) -> None:
    safe_payload = redact_value(dict(payload))
    event = {"v": 1, "type": kind, "task_id": task_id, **safe_payload}
    with (work_dir / "events.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
